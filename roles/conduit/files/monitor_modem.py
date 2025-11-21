#!/usr/bin/env python

"""
MIT License

Copyright (c) 2025 Jeffrey C Honig

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
"""

from __future__ import print_function

import array
import argparse
from contextlib import contextmanager
import errno
import fcntl
import logging
from logging.handlers import SysLogHandler
import os
import psutil
import select
import signal
import socket
import stat
import struct
import subprocess
import sys
import time

if not hasattr(socket, 'SO_BINDTODEVICE'):
    socket.SO_BINDTODEVICE = 25

try:
    FileNotFoundError
except NameError:
    FileNotFoundError = IOError

class LockFileTimeout(Exception):
    def __init__(self, error):
        self.value = error
    def __str__(self):
         return repr(self.value)

class DNSTimeout(Exception):
    def __init__(self, error):
        self.value = error
    def __str__(self):
         return repr(self.value)

# Global flag to indicate shutdown
shutdown_requested = False

def catch_interrupt(signum, frame):
    global shutdown_requested
    logging.warning("Received signal %s, initiating shutdown.", signum)
    shutdown_requested = True

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
            if shutdown_requested or time.time() >= time_end:
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

def daemonize():
    """ Run as a daemon """

    try:
        pid = os.fork()
        if pid > 0:
            # exit first parent
            sys.exit(0)
    except OSError:
        logging.exception("First fork failed")
        return False

    # decouple from parent environment
    os.chdir('/')
    os.setsid()
    os.umask(0)
    # do second fork
    try:
        pid = os.fork()
        if pid > 0:
            # exit from second parent
            sys.exit(0)
    except OSError:
        logging.exception("Second fork failed")
        return False

    # redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()
    si = open(os.devnull, 'r')
    so = open(os.devnull, 'w')
    se = open(os.devnull, 'w')
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())

    return True

def parse_args():
    """ What do we need to do """

    parser = argparse.ArgumentParser(description="Check for errors in Basic Station log")

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
    group.add_argument("-n", "--noop",
                       dest="noop", default=False,
                       action='store_true',
                       help="Don't send notifications, just list what we are going to do")

    group = parser.add_argument_group("Options")
    group.add_argument("--pidfile",
                       dest="pidfile", default="/var/run/conduit_leds.pid",
                       help="Location of the PID file")
    group.add_argument("--interval",
                       default=60.0, type=float,
                       help="Seconds to wait between checks")
    group.add_argument("--hostname",
                       default="ec2-54-221-216-139.compute-1.amazonaws.com",
                       help="Hostname to check")
    group.add_argument("--pings",
                       type=int, default=10,
                       help="Number of pings to receive")
    group.add_argument("--foreground", "-f",
                       dest="foreground", default=False,
                       action='store_true',
                       help="Do not fork; run in foreground")
    group.add_argument("--modem",
                       dest="modem", default="/dev/modem_at1",
                        help="Modem device for Cell service")
    group.add_argument("--real-ppp-on-boot",
                       default="/var/config/ppp/ppp_on_boot",
                       help="Where to link /etc/ppp_on_boot to when enabling ppp")
    group.add_argument("--ppp-on-boot",
                       default="/etc/ppp/ppp_on_boot",
                       help="Where system looks for ppp startup script")
    group.add_argument("--change-script",
                       default="/var/config/ifup_restart",
                       help="Script to run when status changes")
    group.add_argument("--ignore-link-time",
                       default=60*60*3,
                       type=int,
                       help="How often to retry broadcase interfaces if they did not work when we tried them")

    # Parse args
    options = parser.parse_args()

    # --test implies --verbose
    if options.noop:
        options.debug = True

    if options.debug:
        options.verbose = True

    return options

def init_logging(options):
    """ Set up logging """

    logger = logging.getLogger()
    logger.handlers = []
    syslog_format = '%s[%%(process)s]: %%(message)s' % (os.path.basename(sys.argv[0]))
    if not sys.stdout.isatty():
        # Repeat until syslog is available
        while True:
            try:
                syslog_handler = SysLogHandler(address="/dev/log",
                                               facility=SysLogHandler.LOG_DAEMON)
            except FileNotFoundError:
                time.sleep(1)
            else:
                break
            syslog_handler.setFormatter(logging.Formatter(syslog_format))
            logger.addHandler(syslog_handler)
    else:
        logger.addHandler(logging.StreamHandler(stream=sys.stdout))

    if options.debug:
        logger.setLevel('DEBUG')
    elif options.verbose:
        logger.setLevel('INFO')
    else:
        logger.setLevel('WARNING')

# Example usage:
# bytes_sent = sendmsg_with_pktinfo(sock, packet, "8.8.8.8", interface="eth0")
# If you prefer to supply interface index directly, you can call _ifname_to_index("eth0") yourself.
if struct.pack("H",1) == "\x00\x01": # big endian
    def checksum(pkt):
        if len(pkt) % 2 == 1:
            pkt += "\0"
        s = sum(array.array("H", pkt))
        s = (s >> 16) + (s & 0xffff)
        s += s >> 16
        s = ~s
        return s & 0xffff
else:
    def checksum(pkt):
        if len(pkt) % 2 == 1:
            pkt += "\0"
        s = sum(array.array("H", pkt))
        s = (s >> 16) + (s & 0xffff)
        s += s >> 16
        s = ~s
        return (((s>>8)&0xff)|s<<8) & 0xffff

def resolve_with_timeout(hostname, timeout=5):
    def handler(signum, frame):
        raise DNSTimeout("Timeout during name resolution")

    old_handler = signal.signal(signal.SIGALRM, handler)
    signal.alarm(timeout)  # seconds

    ip_addr = None
    try:
        ip_addr = socket.getaddrinfo(hostname, None)[0][4][0]
    except DNSTimeout as error:
        logging.error("resolve_with_timeout: Timeout resolving: %s: %s", hostname, error)
    except socket.gaierror as error:
        logging.error("resolve_with_timeout: error resolving %s: %s", hostname, error)
    else:
        logging.debug("resolve_with_timeout: %s -> %s", hostname, ip_addr)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

    return ip_addr

def icmp_echo(dst_name, interface=None, payload=b'hello', id_=None, seq=1):

    logging.debug("icmp_echo(%s, interface=%s, id=%s, seq=%d)", dst_name, interface, id_, seq)

    if id_ is None:
        id_ = os.getpid() & 0xFFFF

    # raw ICMP socket (IPv4)
    sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)

    if interface is not None:
        # Bind to specific interface (Linux only). Requires root.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, interface.encode() + b'\0')

    # Build ICMP echo request header: type(8)=echo request, code=0, checksum, id, seq
    ICMP_TYPE = 8
    ICMP_CODE = 0
    header = struct.pack('!BBHHH', ICMP_TYPE, ICMP_CODE, 0, id_, seq)
    packet = header + payload
    chksum = checksum(packet)
    header = struct.pack('!BBHHH', ICMP_TYPE, ICMP_CODE, chksum, id_, seq)
    packet = header + payload

    try:
        dst_ip = resolve_with_timeout(dst_name, timeout=1)
    except DNSTimeout:
        return False
    else:
        if dst_ip is None:
            return False

    t0 = time.time()
    try:
        sock.sendto(packet, (dst_ip, 0))
    except socket.gaierror as error:
        logging.error("sendto error: %s", error)
        return False

    deadline = t0 + 10.0
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            return False

        # Wait for the socket to be ready
        try:
            ready, _, _ = select.select([sock], [], [], remaining)
            if not ready:
                logging.debug("icmp_echo: timeout")
                return False
        except (IOError, OSError):
            continue

        # Read pending packets
        while True:
            try:
                recv_packet, addr = sock.recvfrom(65535, socket.MSG_DONTWAIT)
            except (OSError, IOError):
                return False

            iph_len = (struct.unpack("!B", recv_packet[:1])[0] & 0xf) * 4
            icmp_packet = recv_packet[iph_len:]
            if len(icmp_packet) < 8:
                continue
            r_type, r_code, r_chksum, r_id, r_seq = struct.unpack("!BBHHH", icmp_packet[:8])
            logging.debug("RECV type %d code %d id %d seq %d", r_type, r_code, r_id, r_seq)

            if r_type == 0 and r_id == id_ and r_seq == seq:
                return True

    return False

def get_ppp_addresses():
    """
    Returns IP addresses of ppp interfaces
    """

    result = set()

    # Get interface addresses and stats
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()

    for iface, iface_addrs in addrs.items():
        if iface != 'ppp0':
            continue
        iface_stat = stats.get(iface)
        if not iface_stat:
            continue

        # Skip interfaces that are down
        if not iface_stat.isup:
            continue

        # Check for IPv4 with broadcast
        for addr in iface_addrs:
            if addr.family == 2:  # AF_INET (IPv4)
                if addr.address and addr.ptp:
                    result.add(addr.address)

    return result

def get_broadcast_interfaces():
    """
    Returns a list of interface names that:
    - Are up (`isup` flag)
    - Have an IPv4 address assigned
    - Have a broadcast address assigned
    - Have carrier detected (physical link up for Ethernet)
    """
    result = []

    # Get interface addresses and stats
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()

    for iface, iface_addrs in addrs.items():
        iface_stat = stats.get(iface)
        if not iface_stat:
            continue

        # Skip interfaces that are down
        if not iface_stat.isup:
            continue

        # Check for IPv4 with broadcast
        iface_address = None
        for addr in iface_addrs:
            if addr.family == 2:  # AF_INET (IPv4)
                if addr.address and addr.broadcast:
                    iface_address = addr.address
                    break
        if not iface_address:
            continue

        # Check carrier
        carrier_file = "/sys/class/net/{}/carrier".format(iface)
        try:
            with open(carrier_file, 'r') as f:
                carrier = f.read().strip()
                if carrier != '1':
                    continue
        except IOError:
            # If the file doesn't exist, assume link is up (virtual interface)
            pass

        # Passed all checks
        result.append((iface, iface_address))

    return result

def ppp_on_boot(options, enable):
    """ Link or unlink system ppp startup script """

    try:
        ppp_on_boot_stat = os.stat(options.ppp_on_boot)
    except (OSError, IOError):
        logging.error("Unable to get stat info about %s", options.ppp_on_boot)
        return

    logging.debug("ppp_on_boot(%s): %s -> %o", enable, options.ppp_on_boot, ppp_on_boot_stat.st_mode)

    if enable:
        if ppp_on_boot_stat.st_mode & 0o111 != 0o111:
            try:
                os.chmod(options.ppp_on_boot, 0o755)
                logging.info("ppp_on_boot: %s set to executable", options.ppp_on_boot)
            except OSError as error:
                logging.error("Error making %s executable: %s",
                              options.ppp_on_boot,
                              error)
        return

    if ppp_on_boot_stat.st_mode & 0o111 != 0:
        try:
            os.chmod(options.ppp_on_boot, 0o644)
            logging.info("ppp_on_boot: %s set to non-executable", options.ppp_on_boot)
        except OSError as error:
            logging.error("Error making %s non-executable: %s",
                              options.ppp_on_boot,
                              error)

def tunnel_addresses(options):
    """ Return local addresses of all established tunnel connections """

    addresses = set()

    try:
        dst_ip = resolve_with_timeout(options.hostname, timeout=1)
    except DNSTimeout:
        return addresses
    else:
        if dst_ip is None:
            return addresses

    for conn in psutil.net_connections('inet4'):
        if conn.type != socket.SOCK_STREAM:
            continue
        if not conn.raddr:
            continue
        if conn.raddr.port != 22 or conn.raddr.ip != dst_ip:
            continue
        if conn.status != 'ESTABLISHED':
            continue

        addresses.add(conn.laddr.ip)

    return addresses

def check_modem(options):
    """ Run a set of checks """

    have_modem = False
    try:
        modem_stat = os.stat(options.modem)
        if stat.S_ISCHR(modem_stat.st_mode):
            have_modem = True
    except OSError as error:
        logging.error("Unable to stat %s: %s", options.modem, error)

    have_sim = False
    if have_modem:
        cmd = ["radio-cmd", "AT+CPIN?"]
        try:
            output = subprocess.check_output(cmd)
            logging.debug("check_modem: %s returned: %s", " ".join(cmd), output)
        except subprocess.CalledProcessError as error:
            logging.debug("check_modem: %s returned: %s", " ".join(cmd), error)
        if "+CPIN: READY" in output:
            have_sim = True

    logging.debug("have_modem: %s, have_sim: %s", have_modem, have_sim)
    return have_modem, have_sim

def pppd(options, enable):
    """ Start or stop pppd """

    logging.debug("pppd(%s)", enable)

    try:
        subprocess.check_output(["pidof", "pppd"], stderr=subprocess.STDOUT)
        logging.debug("pppd is running")
        ppp_is_running = True
    except subprocess.CalledProcessError:
        logging.debug("pppd is not running")
        ppp_is_running = False

    if enable:
        if not ppp_is_running:
            cmd = ["/etc/init.d/ppp", "start"]
            try:
                logging.info("Running: %s", " ".join(cmd))
                result = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as error:
                logging.error("%s: %s", " ".join(cmd), error)
                return False
            else:
                logging.debug("%s: %s", " ".join(cmd), result.strip())

            for service in [ 'ppp0', 'pppd']:
                cmd = ["/usr/bin/monit", "monitor", service]
                try:
                    logging.info("Running: %s", " ".join(cmd))
                    result = subprocess.check_output(["monit", "monitor", service], stderr=subprocess.STDOUT)
                except subprocess.CalledProcessError as error:
                    logging.error("%s: %s", " ".join(cmd), error)
                else:
                    logging.debug("%s: %s", " ".join(cmd), result.strip())

            return True

        return False

    if ppp_is_running:
        cmd = ["/etc/init.d/ppp", "stop"]
        try:
            logging.info("Running: %s", " ".join(cmd))
            result = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as error:
            logging.error("%s: %s", " ".join(cmd), error)
        else:
            logging.debug("%s: %s", " ".join(cmd), result.strip())

        for service in [ 'ppp0', 'pppd']:
            cmd = ["monit", "unmonitor", service]
            try:
                logging.info("Running: %s", " ".join(cmd))
                result = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as error:
                logging.error("%s: %s", " ".join(cmd), error)
            else:
                logging.debug("%s: %s", " ".join(cmd), result.strip())

        return True

    return False

class IfState(object):
    """ Store IF State """
    def __init__(self, name, address):
        self.name = name
        self.address = address
        self.ignore_time = time.time()
        self.link_state = True
        self.seen = False
        self.seq = -1
        self.responding = None

    def __str__(self):
        return "%s: %s ignore: %f state: %s, seen: %s, seq: %d, responding: %s" % (
            self.name,
            self.address,
            self.ignore_time - time.time(),
            self.link_state,
            self.seen,
            self.seq,
            self.responding)

def get_interface_for_dest(dest_ip):
    """
    Return the outgoing interface name that the kernel would use to
    reach the given destination IP. Uses 'ip route get'.
    """

    try:
        output = subprocess.check_output(
            ["ip", "-4", "route", "get", dest_ip],
            stderr=subprocess.STDOUT
        ).strip()
    except subprocess.CalledProcessError:
        return None

    # Example outputs:
    # "8.8.8.8 via 192.168.1.1 dev eth0 src 192.168.1.10"
    # "192.168.1.50 dev eth0  src 192.168.1.10"
    # "local 192.168.1.100 dev lo  src 192.168.1.100"

    parts = output.split()

    # The interface always follows "dev"
    if "dev" in parts:
        idx = parts.index("dev")
        if idx + 1 < len(parts):
            return parts[idx + 1]

    return None

def process_interface(options, if_state):

    logging.debug("process_interface(%s)", if_state)

    if_state.responding = False

    # Test ping response of default_interface
    # Seq is a unsigned 16 bit integer
    responses = 0
    for ping in range(options.pings):
        if_state.seq = if_state.seq + 1 if if_state.seq < 65535 else 0
        logging.debug("send_icmp (seq %d) via %s", if_state.seq, if_state.name)
        if icmp_echo(options.hostname, interface=if_state.name, seq=if_state.seq):
            responses += 1
            time.sleep(.1)
        if shutdown_requested:
            return

        # Call it good if we get 80% of our pings back
        if responses >= float(options.pings) * 0.80:
            logging.info("Received response on %s, pppd not needed", if_state.name)
            if_state.responding = True
            return

    return

def process(options, progname):
    """ runs tests in a loop """

    if_states = {}
    while time.sleep(options.interval) is None:
        global shutdown_requested
        if shutdown_requested:
            return

        logging.debug("check_modem")

        have_modem, have_sim = check_modem(options)
        if not have_modem or not have_sim:
            logging.info("No Modem or SIM, stopping pppd")
            ppp_on_boot(options, False)
            pppd(options, False)
            continue

        # If we have a modem and sim, ensure ppp_on_boot is enabled
        ppp_on_boot(options, True)

        # Mark interfaces as not seen
        for if_name, if_state in if_states.items():
            if_state.seen = False

        ppp_new_state = True
        do_restart = False
        for if_name, if_address in get_broadcast_interfaces():
            if_state = if_states.setdefault(if_name, IfState(if_name, if_address))

            logging.debug("looking at %s", if_state)

            # Mark as seen
            if_state.seen = True

            # Check if we are supposed to be ignoring this link
            if if_state.ignore_time > time.time():
                logging.info("%s: ignoring", if_name)
                continue

            # Does the default route point here?
            default_if_name = get_interface_for_dest("1.1.1.1")
            if default_if_name == "ppp0":
                # No, tell ppp to stop
                ppp_new_state = False
                logging.info("%s: up, telling ppp to stop", if_name)
                continue
            if default_if_name != if_name:
                # Not at us, continue
                logging.info("%s: up, not default", if_name)
                continue

            # It's us, try pinging
            was_responding = if_state.responding
            process_interface(options, if_state)
            if shutdown_requested:
                return

            if if_state.responding:
                ppp_new_state = False
                logging.info("%s: responding", if_name)

                # Restarte if it's now responding
                if was_responding is False:
                    do_restart = True
                continue

            # Not responding, ignore it for a while
            logging.info("%s: not responding, ignoring", if_name)
            if_state.ignore_time = time.time() + options.ignore_link_time

        # Mark current link state
        active_addresses = set()
        active_ifs = set()
        for if_name, if_state in if_states.items():
            if_state.link_state = if_state.seen
            if if_state.responding:
                active_addresses.add(if_state.address)
                active_ifs.add(if_name)

        # Ensure pppd is in the correct state
        pppd(options, ppp_new_state)

        if do_restart:
            cmd = [options.change_script]
            env = os.environ.copy()
            env["METHOD"] = "monitor_modem"
            if active_ifs:
                env["IFACE"] = ", ".join(list(active_ifs))
            try:
                logging.warning("Running %s", " ".join(cmd))
                subprocess.check_call(cmd, env=env)
            except subprocess.CalledProcessError as error:
                logging.error("%s: %s", " ".join(cmd), error)
        else:
            if ppp_new_state:
                active_addresses = get_ppp_addresses()

            if active_addresses:
                tunnel_addrs = tunnel_addresses(options)
                logging.debug("Checkting that tunnel sources %s is in %s",
                              " ".join(list(tunnel_addrs)),
                              " ".join(list(active_addresses)))
                if not active_addresses.intersection(tunnel_addrs):
                    # No tunnel connections from an active interface
                    cmd = ["/etc/init.d/ssh_tunnel", "restart"]
                    try:
                        logging.warning("Running %s", " ".join(cmd))
                        subprocess.check_call(cmd)
                    except subprocess.CalledProcessError as error:
                        logging.error("%s: %s", " ".join(cmd), error)

def main():
    """It all happens here"""

    progname = os.path.splitext(os.path.basename(sys.argv[0]))[0]

    options = parse_args()

    if not options.foreground:
        if not daemonize():
            return 1

    # Do this after daemonize or we'll hang the system startup.
    init_logging(options)

    # Register signal handlers once (in your main code)
    signal.signal(signal.SIGTERM, catch_interrupt)
    signal.signal(signal.SIGINT, catch_interrupt)

    try:
        with pidfilelock(progname):
            process(options, progname)
    except LockFileTimeout:
        logging.critical("Another instance of %s is running", progname)
        return 1

    return 0

if __name__ == "__main__":
    rc = 1
    try:
        rc = main()
    except KeyboardInterrupt:
        print("")
    except Exception as exc:
        logging.exception(exc)

    sys.exit(rc)
