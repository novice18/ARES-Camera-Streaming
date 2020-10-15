import subprocess
import socket
import re
from contextlib import closing
from UDPsockets.Publisher import Publisher, REQUEST_PORT
from CameraUtils.ProcessMonitor import ProcessMonitor
import logging

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)


class RemoteViewer:
    def get_my_ip(self):
        # a = subprocess.run('ifconfig',capture_output=1)
        # capture_output is only in python 3.7 and above
        ip = None
        try:
            ifconfigAll = subprocess.run(
                'ifconfig', shell=True, stdout=subprocess.PIPE).stdout.strip()
            ip = re.findall(b"192\.168\.1\.[0-9][0-9]?[0-9]?",
                            ifconfigAll)[0].decode("utf-8")
            logging.info("IP: {}".format(ip))

        except FileNotFoundError:
            logging.error("Couldn't find IP. Check if net-tools is installed.")
            ip = "127.0.0.1"

        return ip

    def __init__(self):
        self.pub = Publisher(REQUEST_PORT)

        self.ip = self.get_my_ip()
        self.resolution = (320, 240)

        self.process = ProcessMonitor()
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
            logging.error("Get host")
            return

        self.pub.send({"ip": self.ip,
                       "host": self.remote_host,
                       "resolution": self.resolution,
                       "port": port,
                       "name": self.camera_name})

        # maybe using gdppay instead of rtppay would be faster
        # BUUUT gdp doesn't seem to work on my laptop so let's play safe
        cmd = ('gst-launch-1.0 ' +
               'udpsrc port={} '.format(port) +
               '! application/x-rtp ' +
               '! rtph264depay ' +
               '! h264parse ! avdec_h264 ' +
               '! xvimagesink sync=false')

        self.process.start(cmd)

    def stream(self, hostname, camera_name=None):
        self.remote_host = hostname
        self.camera_name = camera_name
        self.open()

    def read(self):
        # self.monitor(loop= False)
        return self.process.stdout.read(320 * 240 * 3)
