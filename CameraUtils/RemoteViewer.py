import subprocess
import shlex
from enum import Enum
import socket
import re
from contextlib import closing
from UDPsockets.Publisher import Publisher, REQUEST_PORT
import logging

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)


class RemoteViewer:
    OUTPUT = Enum("OUTPUT", "OPENCV WINDOW")

    def get_my_ip(self):
        # a = subprocess.run('ifconfig',capture_output=1)
        # capture_output is only in python 3.7 and above
        m = None
        try:
            a = subprocess.run(
                'ifconfig', stdout=subprocess.PIPE).stdout.strip()
            m = re.search(b"192\.168\.1\.[0-9][0-9][0-9]", a)
        except FileNotFoundError:
            a = b"127\.0\.0\.1"

        if m is not None:
            return m.group()
        else:
            print("Can't find my ip on robot network!")
            return None

    def __init__(self, mode=None):
        if mode is not None:
            mode = self.OUTPUT.WINDOW
        self.mode = mode
        self.pub = Publisher(REQUEST_PORT)

        self.ip = self.get_my_ip()
        self.resolution = (320, 240)

        self.process = None
        self.remote_host = None
        self.camera_name = None

    def close(self):
        if self.remote_host is None:
            logging.info("Error")
            return
        # send 3 times for reliability :P
        self.pub.send({"host": self.remote_host,
                       "cmd": "close", "name": self.camera_name})
        self.pub.send({"host": self.remote_host,
                       "cmd": "close", "name": self.camera_name})
        self.pub.send({"host": self.remote_host,
                       "cmd": "close", "name": self.camera_name})

    def get_free_port(self):
        port = 5001
        while 1:
            try:
                with closing(socket.socket(socket.AF_INET,
                                           socket.SOCK_DGRAM)) as s:
                    s.bind(('', port))
                    return port
            except OSError:
                port += 1
                if port > 7000:
                    raise

    def open(self):
        port = self.get_free_port()
        if self.remote_host is None:
            logging.info("Error")
            return

        self.pub.send({"ip": self.ip,
                       "host": self.remote_host,
                       "resolution": self.resolution,
                       "port": port,
                       "name": self.camera_name})

        if self.mode == self.OUTPUT.WINDOW:
            # caps="application/x-rtp" is what makes things slow.
            # replaces with gdppay
            cmd = 'gst-launch-1.0 udpsrc port={} caps="application/x-rtp", payload=96 ! rtph264depay ! avdec_h264 ! autovideosink sync=false'.format(
                port)
            # cmd = 'gst-launch-1.0 udpsrc port={} ! gdpdepay ! rtph264depay ! avdec_h264 ! autovideosink sync=false'.format(port)
            args = shlex.split(cmd)
            # shell = True need to open a window. $DISPLAY needs to be set?
            # print(args)
            # self.process = subprocess.Popen(cmd, shell=True)
            self.process = subprocess.Popen(args)

        elif self.mode == self.OUTPUT.OPENCV:
            arg = 'gst-launch-1.0 udpsrc port={} caps="application/x-rtp", payload=96 ! rtph264depay ! avdec_h264 ! fdsink sync=false'.format(
                port)
            # cmd = 'gst-launch-1.0 udpsrc port={} ! gdpdepay ! rtph264depay ! avdec_h264 ! fdsink'
            self.process = subprocess.Popen(
                arg, shell=True, stdout=subprocess.PIPE)

    """def __del__(self):
        self.close()
"""

    def stream(self, hostname, camera_name=None):
        self.remote_host = hostname
        self.camera_name = camera_name
        self.open()

        if self.mode == self.OUTPUT.WINDOW:
            self.monitor(loop=True)

    def read(self):
        # self.monitor(loop= False)
        return self.process.stdout.read(320 * 240 * 3)

    def monitor(self, loop=True):
        # TODO
        arg = logging.info("Check")

        if loop:
            while 1:
                self.process.wait()
                self.process = subprocess.Popen(
                    arg, shell=True, stdout=subprocess.PIPE)
                self.open()

        else:
            if self.process.poll():
                return
            else:
                self.process = subprocess.Popen(
                    arg, shell=True, stdout=subprocess.PIPE)
                self.open()
                # resend request
