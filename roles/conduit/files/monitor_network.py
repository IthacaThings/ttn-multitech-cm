#!/usr/bin/env python

"""
MIT License

Copyright (c) 2026 Jeffrey C Honig

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Monitor network connectivity and keep status files for monit.

Every interval this checks the next hop, a list of ping targets, DNS,
the SSH tunnel and the connection to TTN.  Each check that succeeds
touches a file in the status directory, so monit only has to look at
file ages and never blocks on the network.  On a Conduit (MTCDT) the
results are also shown on the LEDs; on other models the LEDs are left
alone.  See https://github.com/IthacaThings/ttn-multitech-cm/issues/137
"""

# Runs on Python 2.7 (mLinux 5), but is kept Python 3 compatible, so
# Python 3 only idioms are not used.
# pylint: disable=consider-using-f-string,unspecified-encoding
# pylint: disable=raise-missing-from,useless-object-inheritance
# pylint: disable=too-many-lines
# cat /sys/devices/platform/mts-io/led-{a, b, c, d} aka {cd, sig1, sig2, sig3}

from __future__ import print_function

import argparse
from contextlib import contextmanager
import errno
import fcntl
import logging
from logging.handlers import SysLogHandler
import os
import re
import select
import signal
import socket
import ssl
import struct
import subprocess
import sys
import threading
import time

import psutil  # pylint: disable=import-error

try:
    FileNotFoundError
except NameError:
    FileNotFoundError = IOError  # pylint: disable=redefined-builtin

IPPROTO_ICMPV6 = getattr(socket, "IPPROTO_ICMPV6", 58)
ICMP_ECHO_REQUEST = 8
ICMP_ECHO_REPLY = 0
ICMP6_ECHO_REQUEST = 128
ICMP6_ECHO_REPLY = 129
PING_PAYLOAD = b"monitor_network"

# sendto() errors that mean there is no route to the target
NO_ROUTE_ERRNOS = (errno.ENETUNREACH, errno.EHOSTUNREACH,
                   errno.EADDRNOTAVAIL, errno.ENETDOWN)

RTF_UP = 0x1
RTF_GATEWAY = 0x2

TCP_ESTABLISHED = "01"

# A neighbour entry confirmed this recently needs no further checking
NEIGH_CONFIRMED_RECENT = 60
# How long the kernel takes to re-check a STALE neighbour entry: 5 s
# of DELAY plus up to three 1 s unicast probes
NEIGH_PROBE_WAIT = 8
NEIGH_RE = re.compile(r"(?:\bused (?P<used>\d+)/(?P<confirmed>\d+)/(?P<updated>\d+)\b.*)?"
                      r"\b(?P<state>PERMANENT|NOARP|REACHABLE|STALE|DELAY|PROBE"
                      r"|FAILED|INCOMPLETE|NONE)\s*$")

# Status files touched when a check succeeds
OK_FILES = ("nexthop", "internet", "tunnel", "ttn")

LED_PATH = "/sys/devices/platform/mts-io/led-a"

# Global flag to indicate shutdown
SHUTDOWN = threading.Event()


class LockFileTimeout(Exception):
    """ Another copy is running """


def catch_interrupt(signum, _frame):
    """ Request a shutdown """
    logging.warning("Received signal %s, initiating shutdown.", signum)
    SHUTDOWN.set()


@contextmanager
def pidfilelock(name):
    """ Context to lock a pid file """

    time_end = time.time() + 30
    pidfile_path = os.path.join("/var/run", name + ".pid")
    fd = os.open(pidfile_path, os.O_RDWR | os.O_CREAT, 0o644)
    lock_file = os.fdopen(fd, "r+")
    while True:
        try:
            logging.debug("Attempting to lock %s", pidfile_path)
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError as err:
            if err.errno != errno.EAGAIN:
                raise err
            logging.debug("Timeout trying to lock: %s", pidfile_path)
            time.sleep(1)
            if time.time() >= time_end:
                raise LockFileTimeout("Unable to lock %s" % pidfile_path)
            continue
        else:
            lock_file.seek(0)
            lock_file.truncate()
            lock_file.write("%d\n" % os.getpid())
            lock_file.flush()
            os.fsync(fd)
            logging.debug("Wrote %d to %s", os.getpid(), pidfile_path)
            break

    try:
        yield lock_file
    finally:
        logging.debug("Unlocking %s", pidfile_path)
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        os.unlink(pidfile_path)
        lock_file.close()


class Defaults(object):  # pylint: disable=too-few-public-methods
    """ Read a /etc/defaults file """

    ROOT = "/etc/default"
    COMMENT_RE = re.compile(r'\s*#.*')
    ASSIGN_RE = re.compile(r'\s*(?P<name>[A-Z][A-Z_0-9]+)=(?P<value>[^#]*)')

    def __init__(self, name):
        self._path = os.path.join(self.ROOT, name)
        self.vars = {}

        with open(self._path, "r") as fp:
            for line in fp:
                line = line.strip()
                if not line or self.COMMENT_RE.match(line):
                    continue
                match = self.ASSIGN_RE.match(line)
                if not match:
                    continue
                value = match.group('value').strip()
                for quote in ["'", '"']:
                    if len(value) >= 2 and value.startswith(quote) and value.endswith(quote):
                        value = value[1:-1]
                        break
                try:
                    value = int(value)
                except ValueError:
                    pass
                self.vars[match.group('name')] = value

    def get(self, name, default=None):
        """ Get a value """

        return self.vars.get(name, default)


class MTSIO(object):
    """ Read MTS IO Values """

    ROOT = '/sys/devices/platform/mts-io'

    def read(self, name):
        """ Read a value """

        with open(os.path.join(self.ROOT, name), "r") as fp:
            return fp.readline().strip()

    def write(self, name, value):
        """ Write a value """

        with open(os.path.join(self.ROOT, name), "w") as fp:
            fp.write("%s\n" % value)


class LEDs(object):
    """ Control LEDs """

    LED_A = 0
    LED_B = 1
    LED_C = 2
    LED_D = 3

    MAP = {
        LED_A: 'led-a',
        LED_B: 'led-b',
        LED_C: 'led-c',
        LED_D: 'led-d'
    }

    def __init__(self, mtsio):
        self._mtsio = mtsio
        self.clearall()

    def change(self, led, new_value):
        """ Set LED on if not on """

        led_key = self.MAP[led]
        old_value = int(self._mtsio.read(led_key))
        if old_value != new_value:
            logging.debug("LEDS: %s %d -> %d", led_key, old_value, new_value)
            self._mtsio.write(led_key, str(new_value))

    def flashall(self, sleep=0.1):
        """ Invert all LEDs for 1 sec """

        save_leds = {}
        for led_key in self.MAP.values():
            old_value = self._mtsio.read(led_key)
            save_leds[led_key] = old_value
            new_value = "0" if old_value == "1" else "1"
            self._mtsio.write(led_key, new_value)

        for led_key in self.MAP.values():
            time.sleep(sleep)
            self._mtsio.write(led_key, save_leds[led_key])

    def show(self, led, value):
        """ Turn an LED on or off """
        self.change(led, 1 if value else 0)

    def clearall(self):
        """ Turn all LEDs off """
        for led in self.MAP:
            self.change(led, 0)


class StateLog(object):  # pylint: disable=too-few-public-methods
    """
    A small log that survives a reboot, for state changes only.

    /var/log is tmpfs, so it can't explain a reboot after the fact.
    The log is kept in two halves of max_size / 2 so it never grows
    past max_size.  reboot_with_reason appends to the same file.
    """

    def __init__(self, path, max_size):
        self._path = path
        self._max_size = max_size // 2

    def write(self, fmt, *args):
        """ Log a message to syslog and the persistent log """

        message = fmt % args
        logging.warning("%s", message)
        if not self._path:
            return
        try:
            directory = os.path.dirname(self._path)
            if not os.path.isdir(directory):
                os.makedirs(directory, 0o755)
            if os.path.exists(self._path) and os.path.getsize(self._path) >= self._max_size:
                os.rename(self._path, self._path + ".1")
            with open(self._path, "a") as fp:
                fp.write("%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), message))
        except (IOError, OSError) as err:
            logging.error("Unable to write %s: %s", self._path, err)


class Result(object):  # pylint: disable=too-few-public-methods
    """ The result of a check: a short state word and some detail """

    def __init__(self, state, detail="", addresses=None):
        self.state = state
        self.detail = detail
        self.addresses = addresses

    @property
    def ok(self):
        """ True if the check passed """
        return self.state == "ok"

    def __str__(self):
        return "%s %s" % (self.state, self.detail) if self.detail else self.state


class CheckThread(threading.Thread):
    """ Run one check in a daemon thread and keep its result """

    def __init__(self, name, func, *args):
        threading.Thread.__init__(self, name=name)
        self.daemon = True
        self._func = func
        self._args = args
        self.result = None

    def run(self):
        try:
            self.result = self._func(*self._args)
        except Exception as exc:  # pylint: disable=broad-except
            logging.exception("%s: %s", self.name, exc)
            self.result = Result("error", str(exc))


class Runner(object):
    """
    Start checks in threads and collect their results by a deadline.

    A check whose thread from an earlier round is still running is not
    started again; it is reported as hung.
    """

    def __init__(self):
        self._threads = {}
        self._started = set()

    def new_round(self):
        """ Forget which checks were started in the last round """
        self._started = set()

    def started(self, name):
        """ True if name was started this round """
        return name in self._started

    def start(self, name, func, *args):
        """ Start a check unless it is still running from an earlier round """

        self._started.add(name)
        thread = self._threads.get(name)
        if thread is not None and thread.is_alive():
            logging.warning("%s: still running from an earlier round", name)
            return
        thread = CheckThread(name, func, *args)
        self._threads[name] = thread
        thread.start()

    def wait(self, name, deadline):
        """ Wait for a check until the deadline and return its Result """

        thread = self._threads.get(name)
        if thread is None or name not in self._started:
            return None
        # Join in slices so a shutdown doesn't wait for the deadline
        while thread.is_alive() and not SHUTDOWN.is_set():
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            thread.join(min(1.0, remaining))
        if thread.is_alive():
            return Result("hung" if thread.result is None else "timeout")
        return thread.result


def daemonize():
    """ Run as a daemon """

    try:
        pid = os.fork()
        if pid > 0:
            # exit first parent
            sys.exit(0)
    except OSError as err:
        logging.exception("First fork failed: %s", err)
        return False

    # decouple from parent environment
    os.chdir('/')
    os.setsid()
    os.umask(0o022)
    # do second fork
    try:
        pid = os.fork()
        if pid > 0:
            # exit from second parent
            sys.exit(0)
    except OSError as err:
        logging.exception("Second fork failed: %s", err)
        return False

    # redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()
    with open(os.devnull, 'r') as si:
        os.dup2(si.fileno(), sys.stdin.fileno())
    with open(os.devnull, 'w') as so:
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(so.fileno(), sys.stderr.fileno())

    return True


def parse_args():
    """ What do we need to do """

    parser = argparse.ArgumentParser(
        description="Monitor network connectivity for monit and the Conduit LEDs")

    #   Debugging
    group = parser.add_argument_group("Debugging options")
    group.add_argument("-d", "--debug",
                       dest="debug", default=False,
                       action='store_true',
                       help="print debugging messages")
    group.add_argument("--nodebug",
                       dest="debug",
                       action='store_false',
                       help="print debugging messages")
    group.add_argument("-v", "--verbose",
                       dest="verbose", default=False,
                       action='store_true',
                       help="print verbose messages")
    group.add_argument("--foreground", "-f",
                       dest="foreground", default=False,
                       action='store_true',
                       help="Do not fork; run in foreground")

    group = parser.add_argument_group("Options")
    group.add_argument("--interval",
                       default=30.0, type=float,
                       help="Seconds between checks")
    group.add_argument("--deadline",
                       type=float,
                       help="Seconds a round of checks may take (default: 2/3 of the interval)")
    group.add_argument("--ping-host",
                       dest="ping_hosts", action="append", default=[],
                       help="IPv4 or IPv6 address to ping; may be repeated")
    group.add_argument("--ping-timeout",
                       default=5.0, type=float,
                       help="Seconds to wait for ping replies")
    group.add_argument("--ttn-host",
                       help="TTN router (router_v3)")
    group.add_argument("--ttn-ports",
                       default="8887,1881",
                       help="Remote ports of the forwarder's connection to TTN")
    group.add_argument("--ttn-probe-port",
                       default=8887, type=int,
                       help="Port for the TLS probe of the TTN router")
    group.add_argument("--ttn-probe-interval",
                       default=600.0, type=float,
                       help="Seconds between TLS probes while the forwarder is connected")
    group.add_argument("--status-dir",
                       default="/run/monitor_network",
                       help="Directory for the status files")
    group.add_argument("--log-file",
                       default="/var/config/log/monitor_network.log",
                       help="Persistent log of state changes")
    group.add_argument("--log-size",
                       default=65536, type=int,
                       help="Maximum size of the persistent log")
    group.add_argument("--want-ppp-file",
                       default="/var/run/using_ppp",
                       help="File to exist if we want to be using PPP")
    group.add_argument("--no-leds",
                       dest="leds", default=True,
                       action='store_false',
                       help="Do not change the LEDs")

    options = parser.parse_args()

    if not options.ping_hosts:
        options.ping_hosts = ["8.8.8.8", "1.1.1.1", "9.9.9.9"]
    if options.deadline is None:
        options.deadline = options.interval * 2 / 3
    options.ttn_ports = set(int(port) for port in options.ttn_ports.split(",") if port)

    return options


def init_logging(options):
    """ Set up logging """

    logger = logging.getLogger()
    syslog_format = '%s[%%(process)s]: %%(threadName)s: %%(message)s' % (
        os.path.basename(sys.argv[0]))
    if not sys.stdout.isatty():
        # Repeat until syslog is available
        while True:
            try:
                syslog_handler = SysLogHandler(address="/dev/log",
                                               facility=SysLogHandler.LOG_DAEMON)
            except (FileNotFoundError, socket.error) as err:
                logging.warning("Unable to open /dev/log: %s, waiting", err)
                time.sleep(1)
            else:
                break
        syslog_handler.setFormatter(logging.Formatter(syslog_format))
        logger.handlers = []
        logger.addHandler(syslog_handler)
    else:
        logger.handlers = []
        logger.addHandler(logging.StreamHandler(stream=sys.stdout))

    if options.debug:
        logger.setLevel('DEBUG')
    elif options.verbose:
        logger.setLevel('INFO')
    else:
        logger.setLevel('WARNING')


#
#	Address helpers
#

def address_family(address):
    """ AF_INET or AF_INET6 for an address literal, None if it isn't one """

    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            socket.inet_pton(family, address)
        except (socket.error, ValueError):
            continue
        return family
    return None


def normalize_address(family, address):
    """ Canonical form of an address, without an IPv6 scope """

    address = address.split("%", 1)[0]
    try:
        return socket.inet_ntop(family, socket.inet_pton(family, address))
    except (socket.error, ValueError):
        return address


def proc_hex_to_address(value):
    """
    Convert an address from /proc/net/{route,tcp,tcp6}.  The kernel
    prints each 32-bit word of the address in host byte order.
    """

    raw = b"".join(struct.pack("=I", int(value[i:i + 8], 16)) for i in range(0, len(value), 8))
    family = socket.AF_INET if len(raw) == 4 else socket.AF_INET6
    return socket.inet_ntop(family, raw)


#
#	ICMP
#

def inet_checksum(data):
    """ RFC 1071 checksum """

    if len(data) % 2:
        data += b"\0"
    total = sum(struct.unpack("!%dH" % (len(data) // 2), data))
    total = (total >> 16) + (total & 0xffff)
    total += total >> 16
    return ~total & 0xffff


SEQUENCE_LOCK = threading.Lock()
SEQUENCE = [0]


def next_sequence():
    """ A sequence number for each set of pings """

    with SEQUENCE_LOCK:
        SEQUENCE[0] = (SEQUENCE[0] + 1) & 0xffff
        return SEQUENCE[0]


def echo_request(family, ident, seq):
    """ Build an ICMP or ICMPv6 echo request """

    if family == socket.AF_INET:
        header = struct.pack("!BBHHH", ICMP_ECHO_REQUEST, 0, 0, ident, seq)
        chksum = inet_checksum(header + PING_PAYLOAD)
        return struct.pack("!BBHHH", ICMP_ECHO_REQUEST, 0, chksum, ident, seq) + PING_PAYLOAD

    # The kernel computes the ICMPv6 checksum
    return struct.pack("!BBHHH", ICMP6_ECHO_REQUEST, 0, 0, ident, seq) + PING_PAYLOAD


def parse_echo_reply(family, packet, ident, seq):
    """ True if packet is a reply to our echo request """

    if family == socket.AF_INET:
        # IPv4 raw sockets include the IP header; ICMPv6 sockets do not
        packet = packet[(ord(packet[0:1]) & 0x0f) * 4:]
        reply_type = ICMP_ECHO_REPLY
    else:
        # ICMPv6 sockets also see neighbour discovery and router
        # advertisements, which we drop here.
        reply_type = ICMP6_ECHO_REPLY
    if len(packet) < 8:
        return False
    r_type, _, _, r_id, r_seq = struct.unpack("!BBHHH", packet[:8])
    return r_type == reply_type and r_id == ident and r_seq == seq


def open_icmp_socket(family):
    """ A raw ICMP socket for the family """

    if family == socket.AF_INET:
        return socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    return socket.socket(socket.AF_INET6, socket.SOCK_RAW, IPPROTO_ICMPV6)


class Pinger(object):
    """
    Ping every target once, in parallel, with one raw socket per
    address family.
    """

    def __init__(self):
        self._ident = os.getpid() & 0xffff
        self._seq = next_sequence()
        self._socks = {}
        self._pending = {}
        self.results = {}

    def send(self, target):
        """ Send an echo request to target """

        family = address_family(target)
        if family is None:
            self.results[target] = Result("error", "not an address")
            return
        try:
            sock = self._socks.get(family)
            if sock is None:
                sock = self._socks[family] = open_icmp_socket(family)
            sock.sendto(echo_request(family, self._ident, self._seq), (target, 0))
        except socket.error as err:
            if err.errno in NO_ROUTE_ERRNOS:
                self.results[target] = Result("no-route")
            else:
                self.results[target] = Result("error", str(err))
            return
        self._pending[(family, normalize_address(family, target))] = (target, time.time())

    def receive(self, sock):
        """ Read one packet and match it to a pending request """

        try:
            packet, addr = sock.recvfrom(2048)
        except socket.error:
            return
        if not parse_echo_reply(sock.family, packet, self._ident, self._seq):
            return
        entry = self._pending.pop((sock.family, normalize_address(sock.family, addr[0])), None)
        if entry:
            target, sent = entry
            self.results[target] = Result("ok", "%.1fms" % ((time.time() - sent) * 1000))

    def wait(self, timeout):
        """ Wait for replies until all have answered or the timeout """

        deadline = time.time() + timeout
        while self._pending and not SHUTDOWN.is_set():
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            try:
                ready, _, _ = select.select(list(self._socks.values()), [], [], remaining)
            except select.error as err:
                if err.args[0] == errno.EINTR:
                    continue
                raise
            for sock in ready:
                self.receive(sock)

        for target, _ in self._pending.values():
            self.results[target] = Result("timeout")
        self._pending = {}

    def close(self):
        """ Close the sockets """

        for sock in self._socks.values():
            sock.close()
        self._socks = {}


def ping(targets, timeout):
    """
    Ping the targets.  Returns {target: Result}, where the state is ok,
    timeout, no-route or error.
    """

    pinger = Pinger()
    try:
        for target in targets:
            pinger.send(target)
        pinger.wait(timeout)
    finally:
        pinger.close()
    return pinger.results


def summarize_pings(results):
    """ One Result per address family: ok if any target answered """

    summary = {}
    for family, key in ((socket.AF_INET, "ping4"), (socket.AF_INET6, "ping6")):
        states = [result.state for target, result in results.items()
                  if address_family(target) == family]
        if not states:
            continue
        if "ok" in states:
            summary[key] = Result("ok")
        elif all(state == "no-route" for state in states):
            # No IPv6 route is not a failure, just not a success
            summary[key] = Result("no-route")
        else:
            summary[key] = Result("fail")
    return summary


#
#	DNS
#

def resolve(hostname):
    """ All addresses of hostname; runs in a thread as it can't be interrupted """

    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror as err:
        return Result("fail", str(err))
    addresses = sorted(set(normalize_address(info[0], info[4][0]) for info in infos))
    return Result("ok", " ".join(addresses), addresses)


#
#	Next hop
#

def default_route():
    """
    The (interface, gateway) of the best IPv4 default route.  The
    gateway is None for a point to point link such as PPP.
    """

    best_metric = None
    best = (None, None)
    with open("/proc/net/route", "r") as fp:
        next(fp)
        for line in fp:
            fields = line.split()
            if len(fields) < 8 or fields[1] != "00000000" or fields[7] != "00000000":
                continue
            flags = int(fields[3], 16)
            if not flags & RTF_UP:
                continue
            gateway = proc_hex_to_address(fields[2]) if flags & RTF_GATEWAY else None
            metric = int(fields[6])
            if best_metric is None or metric < best_metric:
                best_metric = metric
                best = (fields[0], gateway)

    return best


def neighbour_state(gateway, interface):
    """
    The kernel's neighbour state for the gateway and the seconds since
    it was last confirmed.  /proc/net/arp can't tell REACHABLE from
    STALE, so ask ip(8).
    """

    try:
        output = subprocess.check_output(["ip", "-s", "neigh", "show", gateway, "dev", interface],
                                         stderr=subprocess.STDOUT)
    except (OSError, subprocess.CalledProcessError) as err:
        logging.warning("ip neigh show %s: %s", gateway, err)
        return "UNKNOWN", None

    output = output.decode("ascii", "replace").strip()
    if not output:
        return "NONE", None
    match = NEIGH_RE.search(output.splitlines()[0])
    if not match:
        logging.debug("Unable to parse: %s", output)
        return "UNKNOWN", None
    confirmed = match.group("confirmed")
    return match.group("state"), int(confirmed) if confirmed is not None else None


def neighbour_confirmed(state, confirmed):
    """ True if the neighbour entry shows the router answered recently """

    return (state in ("REACHABLE", "PERMANENT", "NOARP")
            or (confirmed is not None and confirmed < NEIGH_CONFIRMED_RECENT))


def check_nexthop():  # pylint: disable=too-many-return-statements
    """
    Is the router present?  Informational only: this never feeds the
    internet check, and a router that drops our packets is normal
    under some policies.
    """

    interface, gateway = default_route()
    if interface is None:
        return Result("fail", "no default route")

    if gateway is None:
        # Point to point (PPP): no neighbour entry; the link state is all we have
        stats = psutil.net_if_stats().get(interface)
        if stats and stats.isup:
            return Result("ok", "%s up" % interface)
        return Result("fail", "%s down" % interface)

    where = "%s %s" % (interface, gateway)

    state, confirmed = neighbour_state(gateway, interface)
    if neighbour_confirmed(state, confirmed):
        return Result("ok", "%s neighbour %s" % (where, state))

    # Make the kernel re-check the entry.  A connect or a refusal both
    # mean the router answered; a timeout proves nothing but starts the
    # DELAY -> PROBE sequence.
    start = time.time()
    try:
        sock = socket.create_connection((gateway, 53), 2)
    except socket.timeout:
        pass
    except socket.error as err:
        if err.errno == errno.ECONNREFUSED:
            return Result("ok", "%s tcp/53 refused" % where)
    else:
        sock.close()
        return Result("ok", "%s tcp/53 open" % where)

    remaining = NEIGH_PROBE_WAIT - (time.time() - start)
    if remaining > 0:
        SHUTDOWN.wait(remaining)

    state, confirmed = neighbour_state(gateway, interface)

    # Ping last, as a bonus: site policy may forbid echo replies
    if ping([gateway], 2)[gateway].ok:
        return Result("ok", "%s icmp" % where)

    if neighbour_confirmed(state, confirmed):
        return Result("silent", "%s neighbour %s" % (where, state))

    return Result("fail", "%s neighbour %s" % (where, state))


#
#	SSH tunnel
#

def check_tunnel(addresses):
    """
    Is autossh's ssh connected to the jump host?  Passive: looks for an
    ESTABLISHED connection to the jump host's SSH port.
    """

    try:
        config = Defaults("ssh_tunnel")
    except IOError:
        return Result("disabled")

    remote_host = config.get("REMOTE_HOST")
    if not remote_host or not config.get("REMOTE_PORT"):
        return Result("disabled")
    ssh_port = int(config.get("SSH_PORT", 22))

    if not addresses:
        return Result("fail", "%s not resolved" % remote_host)

    for conn in psutil.net_connections(kind="tcp"):
        if (conn.status == psutil.CONN_ESTABLISHED and conn.raddr
                and conn.raddr[1] == ssh_port and conn.raddr[0] in addresses):
            return Result("ok", "%s(%s):%d" % (remote_host, conn.raddr[0], ssh_port))

    return Result("fail", "no connection to %s:%d" % (remote_host, ssh_port))


#
#	TTN
#

def established_tcp(ports):
    """
    {inode: (remote, tx_queue, retransmits)} for ESTABLISHED TCP
    connections to any of the remote ports, from /proc/net/tcp{,6}.
    """

    sockets = {}
    for path in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(path, "r") as fp:
                next(fp)
                for line in fp:
                    fields = line.split()
                    if len(fields) < 10 or fields[3] != TCP_ESTABLISHED:
                        continue
                    remote_address, remote_port = fields[2].rsplit(":", 1)
                    port = int(remote_port, 16)
                    if port not in ports:
                        continue
                    remote = "%s:%d" % (proc_hex_to_address(remote_address), port)
                    tx_queue = int(fields[4].split(":")[0], 16)
                    retransmits = int(fields[6], 16)
                    sockets[int(fields[9])] = (remote, tx_queue, retransmits)
        except IOError:
            continue
    return sockets


class TTNConnection(object):  # pylint: disable=too-few-public-methods
    """
    Is the forwarder talking to TTN?  Passive: looks at the forwarder's
    own TCP connection, so it needs no extra traffic.

    Basic Station (port 8887) enables TCP keepalive, so the kernel
    closes a silent connection itself.  mp_pkt_fwd (port 1881) has no
    keepalive but sends status every 30 s, so a dead path shows up as
    retransmissions.  The retransmit count is that of unanswered
    timeouts, reset by an ACK, so unacknowledged data with a non-zero
    count for two rounds in a row means the connection is stuck.
    """

    STUCK_ROUNDS = 2

    def __init__(self, ports):
        self._ports = ports
        self._stuck = {}

    def check(self):
        """ Check the connection """

        sockets = established_tcp(self._ports)
        if not sockets:
            self._stuck = {}
            return Result("fail", "no connection")

        stuck = {}
        good = None
        for inode, (remote, tx_queue, retransmits) in sorted(sockets.items()):
            if retransmits > 0 and tx_queue > 0:
                stuck[inode] = self._stuck.get(inode, 0) + 1
            else:
                stuck[inode] = 0
            detail = "%s tx_queue=%d retransmits=%d" % (remote, tx_queue, retransmits)
            if stuck[inode] < self.STUCK_ROUNDS and good is None:
                good = detail
        self._stuck = stuck

        if good:
            return Result("ok", good)
        return Result("fail", "stuck %s" % detail)


def ttn_probe(host, port, timeout):
    """
    Is TTN itself up?  Active: TLS with a verified certificate and an
    HTTP request; any HTTP response counts.
    """

    context = ssl.create_default_context()
    try:
        sock = socket.create_connection((host, port), timeout)
    except socket.error as err:
        return Result("fail", "connect %s:%d: %s" % (host, port, err))
    try:
        tls = context.wrap_socket(sock, server_hostname=host)
        request = "GET / HTTP/1.1\r\nHost: %s\r\nConnection: close\r\n\r\n" % host
        tls.sendall(request.encode("ascii"))
        response = tls.recv(64)
    except (socket.error, ssl.SSLError, ssl.CertificateError) as err:
        return Result("fail", "%s:%d: %s" % (host, port, err))
    finally:
        sock.close()

    if not response.startswith(b"HTTP/"):
        return Result("fail", "%s:%d: unexpected response %r" % (host, port, response[:16]))
    status_line = response.split(b"\r\n", 1)[0].decode("ascii", "replace")
    return Result("ok", "%s:%d %s" % (host, port, status_line))


#
#	LED inputs
#

def lora_device_path(mtsio):
    """ The device the packet forwarder opens for the LoRa card """

    lora_hwversion = mtsio.read('lora/hw-version')
    if lora_hwversion == "MTAC-LORA-1.0":
        import usb.core  # pylint: disable=import-outside-toplevel,import-error
        dev = usb.core.find(idVendor=0x403, idProduct=0x6014)
        if dev is None:
            logging.warning("No device found for %s", lora_hwversion)
            return None
        device_path = "/dev/bus/usb/%03d/%03d" % (dev.bus, dev.address)
    else:
        device_path = "/run/lora/1/station"
    logging.info("Found %s at %s", lora_hwversion, device_path)
    return device_path


def check_lora(device_path):
    """ Is a process using the LoRa card? """

    if not device_path:
        return False
    with open(os.devnull, 'w') as devnull:
        return subprocess.call(["fuser", device_path],
                               stdout=devnull, stderr=subprocess.STDOUT) == 0


def check_ppp(want_ppp_file):
    """ Does monitor_modem want PPP to be running? """

    return os.path.isfile(want_ppp_file)


#
#	The monitor
#

def diagnose(results):  # pylint: disable=too-many-return-statements
    """ Where is the problem? """

    nexthop = results["nexthop"]
    ping_ok = any(results[key].ok for key in ("ping4", "ping6") if key in results)
    tunnel = results["tunnel"]
    ttn = results["ttn"]
    probe = results.get("ttn-probe")

    if not results["internet"].ok:
        if nexthop.state == "fail":
            return "lan-down"
        return "upstream-down"
    if ttn.state == "disabled" or ttn.ok:
        if ping_ok:
            return "ok"
        if tunnel.ok or ttn.ok:
            return "icmp-filtered"
        return "ok"
    if probe is not None and probe.ok:
        return "station-problem"
    return "ttn-down"


class Monitor(object):  # pylint: disable=too-many-instance-attributes
    """ Run rounds of checks and record the results """

    # Results whose state changes are logged
    LOGGED = ("diagnosis", "nexthop", "ping4", "ping6", "tunnel", "ttn")

    def __init__(self, options, state_log, leds=None, device_path=None):
        self._options = options
        self._log = state_log
        self._leds = leds
        self._device_path = device_path
        self._runner = Runner()
        self._ttn = TTNConnection(options.ttn_ports)
        self._addresses = {}
        self._next_probe = 0
        self._last_probe = None
        self._last_ok = {}
        self._last_states = {}
        self._started = time.time()

        self._ping_hosts = []
        for host in options.ping_hosts:
            if address_family(host) is None:
                self._log.write("Ignoring ping host %s: not an IPv4 or IPv6 address", host)
            else:
                self._ping_hosts.append(host)

        self.init_status_dir()

    def init_status_dir(self):
        """
        Create the status files if they are missing, without updating
        the times of existing ones, so a restart (or a crash loop)
        doesn't reset the reboot timer.  The status directory is tmpfs,
        so after a boot the timers start now.
        """

        if not os.path.isdir(self._options.status_dir):
            os.makedirs(self._options.status_dir, 0o755)
        for name in OK_FILES:
            path = os.path.join(self._options.status_dir, name + ".ok")
            if not os.path.exists(path):
                os.close(os.open(path, os.O_WRONLY | os.O_CREAT, 0o644))

    def touch(self, name):
        """ Record that a check succeeded """

        self._last_ok[name] = time.time()
        path = os.path.join(self._options.status_dir, name + ".ok")
        try:
            os.close(os.open(path, os.O_WRONLY | os.O_CREAT, 0o644))
            os.utime(path, None)
        except OSError as err:
            logging.error("Unable to touch %s: %s", path, err)

    def dns_names(self):
        """ The names to resolve each round """

        names = {}
        if self._options.ttn_host:
            names["ttn"] = self._options.ttn_host
        try:
            remote_host = Defaults("ssh_tunnel").get("REMOTE_HOST")
        except IOError:
            remote_host = None
        if remote_host:
            names["tunnel"] = remote_host
        return names

    def start_probe(self):
        """ Start the TLS probe of the TTN router """

        self._next_probe = time.time() + self._options.ttn_probe_interval
        self._runner.start("ttn-probe", ttn_probe, self._options.ttn_host,
                           self._options.ttn_probe_port, max(1.0, self._options.deadline - 2))

    def run_checks(self):  # pylint: disable=too-many-branches
        """ One round of checks: returns {name: Result} """

        options = self._options
        deadline = time.time() + options.deadline
        runner = self._runner
        runner.new_round()
        results = {}

        # Start the blocking checks in threads
        if self._ping_hosts:
            runner.start("ping", ping, self._ping_hosts, options.ping_timeout)
        names = self.dns_names()
        for key, name in names.items():
            runner.start("dns-" + key, resolve, name)
        runner.start("nexthop", check_nexthop)
        if options.ttn_host and time.time() >= self._next_probe:
            self.start_probe()

        # The tunnel check needs the jump host's address
        for key, name in names.items():
            result = runner.wait("dns-" + key, deadline)
            results["dns-" + key] = result
            if result is not None and result.ok:
                self._addresses[name] = set(result.addresses)

        # The fast checks run here
        tunnel_host = names.get("tunnel")
        if tunnel_host:
            results["tunnel"] = check_tunnel(self._addresses.get(tunnel_host))
        else:
            results["tunnel"] = Result("disabled")
        if options.ttn_host:
            results["ttn"] = self._ttn.check()
            if not results["ttn"].ok and not runner.started("ttn-probe"):
                self.start_probe()
        else:
            results["ttn"] = Result("disabled")

        # Collect the threads
        ping_results = runner.wait("ping", deadline)
        if isinstance(ping_results, dict):
            for target, result in ping_results.items():
                results["ping " + target] = result
            results.update(summarize_pings(ping_results))
        elif ping_results is not None:
            # The ping thread failed or hung
            for host in self._ping_hosts:
                results["ping " + host] = ping_results
            results.update(summarize_pings(dict((host, ping_results) for host in self._ping_hosts)))
        results["nexthop"] = runner.wait("nexthop", deadline)
        probe = runner.wait("ttn-probe", deadline)
        if probe is not None:
            results["ttn-probe"] = probe
            self._last_probe = (time.time(), probe)

        internet = (any(results[key].ok for key in ("ping4", "ping6") if key in results)
                    or results["tunnel"].ok
                    or results["ttn"].ok
                    or (probe is not None and probe.ok))
        results["internet"] = Result("ok" if internet else "fail")

        return results

    def record(self, results, duration):
        """ Touch the status files, write the status file, log changes """

        if results["nexthop"].state in ("ok", "silent"):
            self.touch("nexthop")
        if results["internet"].ok:
            self.touch("internet")
        if results["tunnel"].ok:
            self.touch("tunnel")
        probe = results.get("ttn-probe")
        if results["ttn"].ok or (probe is not None and probe.ok):
            self.touch("ttn")

        diagnosis = Result(diagnose(results))
        results["diagnosis"] = diagnosis

        for key in self.LOGGED:
            if key not in results:
                continue
            state = results[key].state
            if self._last_states.get(key) != state:
                self._log.write("%s: %s", key, results[key])
                self._last_states[key] = state

        self.write_status(results, duration)

    def write_status(self, results, duration):
        """ Replace the status file atomically """

        now = time.time()
        lines = [
            "time: %s" % time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "running: %ds" % (now - self._started),
            "round: %.1fs" % duration,
        ]
        order = ["diagnosis", "internet", "nexthop", "ping4", "ping6"]
        order += sorted(key for key in results if key.startswith("ping "))
        order += sorted(key for key in results if key.startswith("dns-"))
        order += ["tunnel", "ttn", "ttn-probe"]
        for key in order:
            if results.get(key) is not None:
                lines.append("%s: %s" % (key, results[key]))
        if "ttn-probe" not in results and self._last_probe:
            when, probe = self._last_probe
            lines.append("ttn-probe: %s (%ds ago)" % (probe, now - when))
        for name in OK_FILES:
            if name in self._last_ok:
                lines.append("last-ok %s: %ds ago" % (name, now - self._last_ok[name]))

        path = os.path.join(self._options.status_dir, "status")
        temp = path + ".tmp"
        try:
            with open(temp, "w") as fp:
                fp.write("\n".join(lines) + "\n")
            os.rename(temp, path)
        except (IOError, OSError) as err:
            logging.error("Unable to write %s: %s", path, err)

    def show_leds(self, results):
        """ A = PPP, B = tunnel, C = forwarder, D = DNS """

        if not self._leds:
            return
        self._leds.show(LEDs.LED_A, check_ppp(self._options.want_ppp_file))
        self._leds.show(LEDs.LED_B, results["tunnel"].ok)
        self._leds.show(LEDs.LED_C, check_lora(self._device_path))
        dns = results.get("dns-ttn")
        self._leds.show(LEDs.LED_D, dns is not None and dns.ok)

    def round(self):
        """ Check everything and record the results """

        start = time.time()
        results = self.run_checks()
        self.record(results, time.time() - start)
        self.show_leds(results)

    def run(self):
        """ Run rounds every interval, flashing the LEDs in between """

        interval = self._options.interval
        next_time = time.time()
        while not SHUTDOWN.is_set():
            now = time.time()
            if now >= next_time:
                while next_time <= now:
                    next_time += interval
                logging.debug("Checking status")
                self.round()
            elif self._leds:
                self._leds.flashall()
            duration = min(5.0, next_time - time.time())
            if duration > 0:
                SHUTDOWN.wait(duration)


def main():
    """It all happens here"""

    progname = os.path.splitext(os.path.basename(sys.argv[0]))[0]

    options = parse_args()

    if not options.foreground:
        if not daemonize():
            return 1

    # Do this after daemonize or we'll hang the system startup.
    init_logging(options)

    signal.signal(signal.SIGTERM, catch_interrupt)
    signal.signal(signal.SIGINT, catch_interrupt)

    # The default reserves 8 MB of virtual memory per thread
    threading.stack_size(256 * 1024)

    state_log = StateLog(options.log_file, options.log_size)

    try:
        with pidfilelock(progname):
            state_log.write("%s: started", progname)
            leds = None
            device_path = None
            if options.leds and os.path.exists(LED_PATH):
                mtsio = MTSIO()
                device_path = lora_device_path(mtsio)
                leds = LEDs(mtsio)
            try:
                Monitor(options, state_log, leds, device_path).run()
            finally:
                if leds:
                    LEDs(MTSIO())
            state_log.write("%s: stopped", progname)
    except LockFileTimeout:
        logging.critical("Another instance of %s is running", progname)
        return 1

    return 0


def run():
    """ Run main and turn exceptions into an exit code """

    try:
        return main()
    except KeyboardInterrupt:
        print("")
    except Exception as exc:  # pylint: disable=broad-except
        logging.exception(exc)
    return 1


if __name__ == "__main__":
    sys.exit(run())
