#!/usr/bin/env python

"""
MIT License

Copyright (c) 2024 Jeffrey C Honig

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

# cat /sys/devices/platform/mts-io/led-{a, b, c, d} aka {cd, sig1, sig2, sig3}

import argparse
from contextlib import contextmanager
import errno
import fcntl
import logging
from logging.handlers import SysLogHandler
import os
import pprint
import psutil
import re
import socket
import stat
import struct
import subprocess
import sys
import time

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
               
class Defaults(object):
    """ Read a /etc/defaults file """

    ROOT = "/etc/default"
    COMMENT_RE=re.compile(r'\s*#.*')
    ASSIGN_RE=re.compile(r'\s*(?P<name>[A-Z][A-Z_0-9]+)=(?P<value>[^#]*)')

    def __init__(self, name):
        self._name = name
        self._path = os.path.join(self.ROOT, self._name)
        self.vars = {}

        with open(self._path, "r") as fp:
            for line in fp:
                line = line.strip()
                if len(line) == 0 or self.COMMENT_RE.match(line):
                    continue
                logging.debug("Defaults: %s: %s", self._path, line)
                match = self.ASSIGN_RE.match(line)
                if not match:
                    continue
                value = match.group('value')
                try:
                    value = int(value)
                except ValueError:
                    pass
                try:
                    for quote in ["'", '"']:
                        if value.startswith(quote) and value.endswith(quote):
                            value = value[1:-1]
                except AttributeError:
                    pass
                self.vars[match.group('name')] = value

    def get(self, name, default=None):
        """ Get a value """

        if name in self.vars:
            return self.vars[name]

        return default

class MTSIO(object):
    """ Read MTS IO Values """

    ROOT = '/sys/devices/platform/mts-io'
    def __init__(self):
        pass

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

    LED_A=0
    LED_B=1
    LED_C=2
    LED_D=3

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

        logging.debug("LEDs: change %d -> %d", led, new_value)

        led_key = self.MAP[led]
        old_value = int(self._mtsio.read(led_key))
        logging.debug("LEDS: read %d", old_value)
        if old_value != new_value:
            logging.debug("LEDS: write %d", new_value)
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
            old_value = save_leds[led_key]
            self._mtsio.write(led_key, old_value)

    def set(self, led):
        self.change(led, 1)

    def clear(self, led):
        self.change(led, 0)

    def clearall(self):
        for led in range(4):
            self.clear(led)

def daemonize():
    """ Run as a daemon """

    try:
        pid = os.fork()
        if pid > 0:
            # exit first parent
            sys.exit(0)
    except OSError as err:
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
    except OSError as err:
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
                       default="google.com",
                       help="Hostname to check")
    group.add_argument("--foreground", "-f",
                       dest="foreground", default=False,
                       action='store_true',
                       help="Do not fork; run in foreground")
    group.add_argument("--modem",
                       dest="modem", default="/dev/modem_at0",
                        help="Modem device for Cell service")

    # Parse args
    options = parser.parse_args()

    if options.noop:
        options.debug = True

    # Init Logging
    init_logging(options)

    return options

def check_tunnel(options):
    """ Check tunnel status """

    global cached_ip

    try:
        config = Defaults("ssh_tunnel")
    except IOError:
        cached_ip = None
        return False

    local_port = config.get('LOCAL_PORT')
    if not local_port:
        cached_ip = None
        return False
    remote_host = config.get('REMOTE_HOST')
    if not remote_host:
        cached_ip = None
        return False
    try:
        remote_ip = socket.gethostbyname(remote_host)
        cached_ip = remote_ip
    except socket.gaierror:
        if not cached_ip:
            logging.info("check_tunnel: Unable to resolve %s", remote_host)
            return False
        remote_host = cached_ip
        logging.info("check_tunnel: Using cached IP %s", remote_host)

    for conn in psutil.net_connections():
        if conn.type == socket.SOCK_STREAM and conn.status == psutil.CONN_ESTABLISHED and conn.raddr == (remote_ip, local_port):
            logging.info("check_tunnel: Found connection to %s(%s):%s with PID %d",
                         remote_host,
                         remote_ip,
                         local_port,
                         conn.pid)
            return True

    logging.info("check_tunnel: No connection found to %s(%s):%s", remote_host, remote_ip, local_port)
    return False

def check_dns(options):
    """ Check dns status """

    try:
        host_ip = socket.gethostbyname(options.hostname)
        logging.info("check_dns: %s resolved to %s", options.hostname, host_ip)
    except socket.gaierror:
        logging.info("check_dns: %s failed to resolve", options.hostname)
        return False

    return True

def check_lora(options, device_path):
    """ Check LoRa status """

    cmd = ["fuser", device_path]
    DEVNULL = open(os.devnull, 'w')
    try:
        subprocess.check_call(cmd,
                              stdout=DEVNULL,
                              stderr=subprocess.STDOUT)
        logging.info("check_lora: fuser %s returned 0", device_path)
    except subprocess.CalledProcessError:
        logging.info("check_lora: fuser %s returned non-zero", device_path)
        return False

    return True

def check_ppp(options):
    """ Check status of ppp connection """

    try:
        modem_stat = os.stat(options.modem)
        if not stat.S_ISCHR(modem_stat.st_mode):
            logging.debug("check_ppp: %s not a character device", options.modem)
            return False
    except OSError as error:
        logging.debug("check_ppp: %s: %s", options.modem, error)
        return False

    peer_addr = None
    for ifname, ifaddrs in psutil.net_if_addrs().items():
        if ifname != "ppp0":
            continue
        for ifaddr in ifaddrs:
            if ifaddr.family != socket.AF_INET:
                continue
            if ifaddr.ptp is None:
                continue
            if ifaddr.ptp == "10.64.64.64":
                continue
            peer_addr = ifaddr.ptp
        break

    if not peer_addr:
        logging.debug("check_ppp: No valid peer address found")
        return False

    return True    

def process(options, leds, device_path):
    """ Check all the services """

    if check_dns(options):
        leds.set(LEDs.LED_D)
    else:
        leds.clear(LEDs.LED_D)

    if device_path and check_lora(options, device_path):
        leds.set(LEDs.LED_C)
    else:
        leds.clear(LEDs.LED_C)

    if check_tunnel(options):
        leds.set(LEDs.LED_B)
    else:
        leds.clear(LEDs.LED_B)

    if check_ppp(options):
        leds.set(LEDs.LED_A)
    else:
        leds.clear(LEDs.LED_A)

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

def main():
    """It all happens here"""

    progname = os.path.basename(sys.argv[0])

    options = parse_args()

    if not options.foreground:
        if not daemonize():
            return 1

    mtsio = MTSIO()

    hwversion = mtsio.read('hw-version')
    if not hwversion.startswith("MTCDT-"):
        logging.critical("Not running on a conduit: %s", hwversion)
        return 1

    # Find the device for the LoRA concentrator
    lora_hwversion = mtsio.read('lora/hw-version')
    if lora_hwversion == "MTAC-LORA-1.0":
        import usb.core
        dev = usb.core.find(idVendor=0x403, idProduct=0x6014)
        if dev is not None:
            device_path = "/dev/bus/usb/%03d/%03d" % (dev.bus, dev.address)
        else:
            device_path = None
    else:
        device_path = "/run/lora/1/station"
    if device_path:
        logging.info("Found %s at %s", lora_hwversion, device_path)
    else:
        logging.warning("No device found for %s", lora_hwversion)

    try:
        with pidfilelock(progname) as pid_file:
            leds = LEDs(mtsio)

            # XXX - Spread the tests out over 1/4 of the interval?
            # XXX - Ping the remote side of the PPP connection?  Requires exec

            next_time = time.time()
            while True:
                if time.time() > next_time:
                    while time.time() > next_time:
                        next_time += options.interval
                    logging.debug("Checking status")
                    process(options, leds, device_path)
                else:
                    logging.debug("Flashing LEDs")
                    leds.flashall()
                duration = min(5.0, next_time - time.time())
                logging.debug("Sleeping for %f seconds", duration)
                time.sleep(duration)
    except LockFileTimeout:
        logging.critical("Another instance of %s is running", progname)
        return 1

if __name__ == "__main__":

    rc = 1
    try:
        rc = main()
    except KeyboardInterrupt:
        print("")
        LEDs(MTSIO())
    except Exception:
        LEDs(MTSIO())

    sys.exit(rc)
