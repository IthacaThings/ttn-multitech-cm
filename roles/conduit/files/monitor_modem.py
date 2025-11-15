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
import binascii
from contextlib import contextmanager
import errno
import fcntl
import ipaddress
import logging
from logging.handlers import SysLogHandler
import os
import select
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

@contextmanager
def pidfilelock(name):
    """ Context to lock a pid file """

    time_left = 30
    pidfile_path = os.path.join("/var/run", name + ".pid")
    lock_file = open(pidfile_path, 'w+')
    while True:
        try:
            logging.debug("Attempting to lock %s", pidfile_path)
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_file.write(str(os.getpid()) + '\n')
            lock_file.flush()
            logging.debug("Wrote %d to %s", os.getpid(), pidfile_path)
            break
        except IOError as err:
            if err.errno != errno.EAGAIN:
                raise err
            else:
                logging.debug("Timeout trying to lock", pidfile_path)
                time.sleep(1)
                time_left -= 1
                if time_left == 0:
                    raise LockFileTimeout("Unable to lock %s" % pidfile_path)

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

    # Parse args
    options = parser.parse_args()

    # --test implies --verbose
    if options.noop:
        options.debug = True

    # Init Logging
    init_logging(options)

    return options

def init_logging(options):
    """ Set up logging """

    logger = logging.getLogger()
    logger.handlers = []
    syslog_format = '%s[%%(process)s]: %%(message)s' % (os.path.basename(sys.argv[0]))
    syslog_handler = SysLogHandler(address="/dev/log",
                                   facility=SysLogHandler.LOG_DAEMON)
    syslog_handler.setFormatter(logging.Formatter(syslog_format))
    if not sys.stdout.isatty():
        logger.addHandler(syslog_handler)
    else:
        logger.addHandler(logging.StreamHandler(stream=sys.stdout))

    if options.debug:
        logger.setLevel('DEBUG')
    elif options.verbose:
        logger.setLevel('INFO')
    else:
        logger.setLevel('WARNING')

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

def icmp_echo(dst_ip, interface = None, payload = b'hello', id_ = None, seq = 1):
    if id_ is None:
        id_ = os.getpid() & 0xFFFF

    # raw ICMP socket (IPv4)
    sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)

    if interface is not None:
        # Bind to specific interface (Linux only). Requires root.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, interface.encode() + b'\0')

    # Build ICMP echo request header: type(8)=echo request, code=0, checksum, id, seq
    icmp_type = 8
    icmp_code = 0
    header = struct.pack('!BBHHH', icmp_type, icmp_code, 0, id_, seq)
    packet = header + payload
    chksum = checksum(packet)
    header = struct.pack('!BBHHH', icmp_type, icmp_code, chksum, id_, seq)
    packet = header + payload

    t0 = time.time()
    sock.sendto(packet, (dst_ip, 0))

    deadline = t0 + 10.0
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            return False

        # Ignore errno 4
        try:
            ready, _, _ = select.select([sock], [], [], remaining)
            if not ready:
                logging.debug("TIMEOUT")
                return False
        except (IOError, OSError):
            continue

        recv_packet, addr = sock.recvfrom(65535)

        iph_len = (struct.unpack("!B", recv_packet[:1])[0] & 0xf) * 4
        icmp_packet = recv_packet[iph_len:]
        if len(icmp_packet) < 8:
            continue
        r_type, r_code, r_chksum, r_id, r_seq = struct.unpack("!BBHHH", icmp_packet[:8])
        logging.debug("RECV type %d code %d id %d seq %d", r_type, r_code, r_id, r_seq)

        if r_type == 0 and r_id == id_ and r_seq == seq:
            return True

    return False

def set_rpfilter(options, value, interfaces):
    """ Set values of rp_filter on the specified interface(s) """

    for interface in interfaces:
        try:
            with open("/proc/sys/net/ipv4/conf/%s/rp_filter" % interface, "w") as fp:
                fp.write(str(value))
        except FileNotFoundError:
            pass

class Route(object):
    """ A routing table entry """

    def __init__(self, header, parts):

        self._parts = {}

        for key, value in zip(header, parts):
            if key == 'Iface':
                self.__setattr__(key, value)
            elif key in ['Destination', 'Gateway', 'Mask']:
                self.__setattr__(key, ipaddress.ip_address(binascii.unhexlify(value)[::-1]))
            elif key == 'Flags':
                self.__setattr__(key, int(value, 16))
            else:
                self.__setattr__(key, int(value))

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "Iface: %s Destination %s Gateway %s Flags %x RefCnt %d Use %d Metric %d Mask %s MTU %d Window %d IRTT %d" % (
            self.Iface,
            self.Destination,
            self.Gateway,
            self.Flags,
            self.RefCnt,
            self.Use,
            self.Metric,
            self.Mask,
            self.MTU,
            self.Window,
            self.IRTT)

def read_routes(options):
    """ Read the routing table """

    _rt = []

    with open("/proc/net/route", "r") as fp:
        header = []
        for line in fp:
            if len(line.strip()) == 0:
                continue
            parts = line.split()
            if not header:
                header = parts
                continue
            route = Route(header, parts)
            _rt.append(route)

    return _rt

def ppp_on_boot(options, enable):
    """ Link or unlink system ppp startup script """

    try:
        link_target = os.readlink(options.ppp_on_boot)
    except (OSError, IOError):
        link_target = None

    logging.debug("ppp_on_boot(%s): %s -> %s", enable, options.ppp_on_boot, link_target)

    if enable:
        if link_target and link_target != options.real_ppp_on_boot:
            try:
                os.unlink(options.ppp_on_boot)
                os.symlink(options.real_ppp_on_boot, options.ppp_on_boot)
                logging.debug("ppp_on_boot: %s linked", options.ppp_on_boot)
            except OSError as error:
                logging.error("Error linking %s -> %s",
                              options.ppp_on_boot,
                              options.real_ppp_on_boot,
                              error)
            return

    if link_target:
        try:
            os.unlink(options.ppp_on_boot)
            logging.debug("ppp_on_boot: %s un-linked", options.ppp_on_boot)
        except OSError as error:
            logging.error("Error un-linking %s",
                          options.ppp_on_boot,
                          error)

def check_modem(options):
    """ Run a set of checks """

    have_modem = False
    try:
        modem_stat = os.stat(options.modem)
        if stat.S_ISCHR(modem_stat.st_mode):
            have_modem = True
    except OSError:
        pass

    have_sim = False
    if have_modem:
        cmd = ["radio-cmd", "AT+CPIN?"]
        try:
            output = subprocess.check_output(cmd)
            logging.info("check_modem: %s returned: %s", " ".join(cmd), output)
        except subprocess.CalledProcessError as error:
            logging.debug("check_modem: %s returned: %s", " ".join(cmd), error)
        if "+CPIN: READY" in output:
            have_sim = True

    logging.debug("have_modem: %s, have_sim: %s", have_modem, have_sim)
    return have_modem, have_sim

def pppd(options, enable):
    """ Start or stop pppd """

    logging.debug("pppd(%s)", enable)

    ppp_on_boot(options, enable)

    try:
        subprocess.check_call(["pidof", "pppd"])
        logging.debug("pppd is running")
        ppp_is_running = True
    except subprocess.CalledProcessError:
        logging.debug("pppd is not running")
        ppp_is_running = False

    if enable:
        if not ppp_is_running:
            try:
                logging.debug("Starting %s", options.ppp_on_boot)
                subprocess.check_call([options.ppp_on_boot])
            except subprocess.CalledProcessError as error:
                logging.error("Starting %s: %s", options.ppp_on_boot, error)
                return

        for service in [ 'ppp0', 'pppd']:
            try:
                logging.debug("Monitoring %s", service)
                subprocess.check_call(["monit", "monitor", service])
            except subprocess.CalledProcessError as error:
                logging.error("Monitoring %s: %s", service, error)

        return

    if ppp_is_running:
        cmd = ["/etc/init.d/ppp", "stop"]
        try:
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError as error:
            logging.error("%s: %s", " ".join(cmd), error)
            pass

    for service in [ 'ppp0', 'pppd']:
        cmd = ["monit", "unmonitor", service]
        try:
            logging.debug("Unonitoring %s", service)
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError as error:
            logging.error("%s: %s", " ".join(cmd), error)
            pass

def main():
    """It all happens here"""

    options = parse_args()

    if not options.foreground:
        if not daemonize():
            return 1

    # Read the routing table and figure out if we have a non-ppp
    # interface with a default route.  This will tell us which is the
    # primary interface.
    rt = read_routes(options)
    for route in rt:
        if route.Flags & 0x3 != 0x3:
            continue
        if str(route.Destination) != "0.0.0.0":
            continue
        if route.Iface == "ppp0":
            continue
        default_interface = route.Iface
        logging.info("Using a default interface of %s", default_interface)
        break
    else:
        logging.fatal("Unable to find a non-ppp interface with a default route")
        return 1

    # Set rp_filter to allow RFC3704 Losse Reverse Path Each so we can
    # receive pings that are not from the expected interface
    set_rpfilter(options, 2, ["all", "default", default_interface, "ppp0"])

    seq = -1
    while time.sleep(options.interval) is None:

        logging.debug("check_modem")
        have_modem, have_sim = check_modem(options)
        if not have_modem or not have_sim:
            logging.warning("NO Modem or SIM, stopping pppd")
            pppd(options, False)
            continue

        # Test ping response of default_interface
        # Seq is a unsigned 16 bit integer
        responses = 0
        for ping in range(options.pings):
            seq = seq + 1 if seq < 65535 else 0
            logging.debug("send_icmp (seq %d) via %s", seq, default_interface)
            if icmp_echo(options.hostname, interface=default_interface, seq=seq):
                responses += 1
            time.sleep(.1)
        # Call it good if we get 80% of our pings back
        if responses >= float(options.pings) * 0.80:
            logging.warning("Received response on %s, stopping pppd", default_interface)
            pppd(options, False)
            continue

        logging.warning("No response received on %s, starting pppd", default_interface)
        pppd(options, True)
        continue

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



# # # # XXX Adapt this and keep track of connection duration (by address and port)

def parse_ip_port(hex_ip, hex_port):
    ip = socket.inet_ntoa(struct.pack("<L", int(hex_ip, 16)))
    port = int(hex_port, 16)
    return ipaddress.ip_address(ip), port

def get_inode_to_process():
    """Return dict mapping socket inode -> (pid, process_name)."""
    inode_map = {}
    for pid in filter(str.isdigit, os.listdir("/proc")):
        fd_dir = os.path.join("/proc", pid, "fd")
        comm_file = os.path.join("/proc", pid, "comm")
        try:
            with open(comm_file, "r") as f:
                pname = f.read().strip()
        except IOError:
            pname = "unknown"
        try:
            for fd in os.listdir(fd_dir):
                path = os.path.join(fd_dir, fd)
                try:
                    target = os.readlink(path)
                    if target.startswith("socket:["):
                        inode = target[8:-1]
                        inode_map[inode] = (int(pid), pname)
                except OSError:
                    continue
        except OSError:
            continue
    return inode_map

def get_established_tcp_connections():
    results = []
    inode_map = get_inode_to_process()
    with open("/proc/net/tcp", "r") as f:
        next(f)  # skip header
        for line in f:
            parts = line.split()
            local_ip, local_port = parts[1].split(":")
            remote_ip, remote_port = parts[2].split(":")
            state = parts[3]
            inode = parts[9]
            if state != "01":  # only ESTABLISHED
                continue
            lip, lport = parse_ip_port(local_ip, local_port)
            rip, rport = parse_ip_port(remote_ip, remote_port)
            proc = inode_map.get(inode, (None, None))
            results.append({
                "local": (str(lip), lport),
                "remote": (str(rip), rport),
                "pid": proc[0],
                "program": proc[1]
            })
    return results

# Example usage
if __name__ == "__main__":
    conns = get_established_tcp_connections()
    for c in conns:
        print("%s:%d -> %s:%d (pid=%s, program=%s)" %
              (c["local"][0], c["local"][1],
               c["remote"][0], c["remote"][1],
               c["pid"], c["program"]))
