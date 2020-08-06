import socket
import struct
from collections import namedtuple

from time import monotonic
import shlex
import os
import subprocess
import signal
import re
from enum import Enum
import time
from contextlib import closing

import msgpack

import logging
logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)

try:
    from imutils.video import VideoStream, FileVideoStream
    import cv2, imutils
except ImportError:
    cv2 = None

timeout = socket.timeout

MAX_SIZE = 65507
REQUEST_PORT = 5000

class Publisher:
    def __init__(self, port):
        """ Create a Publisher Object
        Arguments:
            port         -- the port to publish the messages on
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.broadcast_ip = "127.0.0.1"
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        #self.broadcast_ip = "192.168.1.43"

        self.sock.settimeout(0.2)
        self.sock.connect((self.broadcast_ip, port))

        self.port = port

    def send(self, obj):
        """ Publish a message. The obj can be any nesting of standard python types """
        msg = msgpack.dumps(obj, use_bin_type=False)
        assert len(msg) < MAX_SIZE, "Encoded message too big!"
        self.sock.send(msg)

    def __del__(self):
        self.sock.close()


class Subscriber:
    def __init__(self, port, timeout=0.2):
        """ Create a Subscriber Object
        Arguments:
            port         -- the port to listen to messages on
            timeout      -- how long to wait before a message is considered out of date
        """
        self.max_size = MAX_SIZE

        self.port = port
        self.timeout = timeout

        self.last_data = None
        self.last_time = float('-inf')

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

        self.sock.settimeout(timeout)
        self.sock.bind(("", port))

    def recv(self):
        """ Receive a single message from the socket buffer. It blocks for up to timeout seconds.
        If no message is received before timeout it raises a timeout exception"""

        try:
            self.last_data, address = self.sock.recvfrom(self.max_size)
        except BlockingIOError:
            raise socket.timeout("no messages in buffer and called with timeout = 0")

        self.last_time = monotonic()
        return msgpack.loads(self.last_data, raw=USING_PYTHON_2)

    def get(self):
        """ Returns the latest message it can without blocking. If the latest massage is
            older then timeout seconds it raises a timeout exception"""
        try:
            self.sock.settimeout(0)
            while True:
                self.last_data, address = self.sock.recvfrom(self.max_size)
                self.last_time = monotonic()
        except socket.error:
            pass
        finally:
            self.sock.settimeout(self.timeout)

        current_time = monotonic()
        if (current_time - self.last_time) < self.timeout:
            return msgpack.loads(self.last_data, raw=USING_PYTHON_2)
        else:
            raise socket.timeout("timeout=" + str(self.timeout) + \
                                 ", last message time=" + str(self.last_time) + \
                                 ", current time=" + str(current_time))

    def get_list(self):
        """ Returns list of messages, in the order they were received"""
        msg_bufer = []
        try:
            self.sock.settimeout(0)
            while True:
                self.last_data, address = self.sock.recvfrom(self.max_size)
                self.last_time = monotonic()
                msg = msgpack.loads(self.last_data)
                msg_bufer.append(msg)
        except socket.error:
            pass
        finally:
            self.sock.settimeout(self.timeout)

        return msg_bufer

    def __del__(self):
        self.sock.close()

####### Camera
class ProcessMonitor:
    def __init__(self):
        self.process = None
        self.cmd = None

    def start(self, cmd):
        self.cmd = cmd
        if(self.process!=None):
            self.stop()

        # setting preexec_fn=os.setsid allows us to kill the process group allowing for shell=True
        # without it calling process.terminate() would only kill the shell and not the underlying process
        self.process = subprocess.Popen(self.cmd, shell=True, stdin=subprocess.PIPE, preexec_fn=os.setsid)

        # shell=True is needed as some commands have a shell pipe in them (raspivid specifically)
        # self.process = subprocess.Popen(shlex.split(self.cmd), stdin=subprocess.PIPE)

    def stop(self):
        if self.process != None:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            time.sleep(1)
            while self.running():
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
        self.process = None

    def restart(self):
        self.start(self.cmd)

    def running(self):
        return self.process.poll() == None

class Server:
    INPUT = Enum("INPUT", "RPI_CAM USB_CAM OPENCV USB_H264")
    def __init__(self, name = None, device = None):
        if device == None:
            device = "/dev/video0"

        self.mode = self.INPUT.USB_CAM
        self.name = name
        self.device = device

        self.sub = Subscriber(REQUEST_PORT, timeout=0)
        self.hostname = subprocess.run('hostname', stdout=subprocess.PIPE).stdout.strip().decode("utf-8")

        self.process = ProcessMonitor()


    def parse_messages(self):
        messages = self.sub.get_list()
        for msg in messages:
            if msg['host'] ==  self.hostname:
                if msg.get('name') != self.name: # get returns None when key not found
                    continue
                logging.info("got ", msg)
                if msg.get('cmd') ==  'close':
                    self.process.stop()
                else:
                    time.sleep(1) # sleep is necessary to not race ahead of viewer
                    cmd = self.get_cmd(msg)
                    self.process.start(cmd)

    def listen(self):
        while 1:
            self.parse_messages()

    """ display new image array on remote viewer """
    def imshow(self, name, img):
        self.parse_messages()

        if self.process.process is None:
            logging.info("No viewer connected")
            return

        img = imutils.resize(img, width=320) # resolution needs to match with video
        self.process.process.stdin.write(cv2.cvtColor(img, cv2.COLOR_BGR2YUV_I420))

    def get_cmd(self, msg):
        port, ip = msg["port"] , msg["ip"]

        """
        I think this might also give a low latency stream, haven't tried it tho:
        $ gst-launch-1.0 v4l2src device={} bitrate=1000000 \
        ! 'video/x-h264,width=640,height=480' \
        ! h264parse \
        ! queue \
        ! rtph264pay config-interval=1 pt=96 \
        ! gdppay \
        ! udpsink host=[MY IP] port=5000

        And on the receiving end:
        gst-launch-1.0 udpsrc port=5000 \
        ! gdpdepay \
        ! rtph264depay \
        ! avdec_h264 \
        ! videoconvert \
        ! autovideosink sync=false

        P.S. I also haven't calculated the exact latency in ms.
        """
        try:
            cmd = ("gst-launch-1.0 v4l2src device={} ! video/x-raw,width=640,height=480 ".format(self.device) +\
                   "! x264enc bitrate=100000 speed-preset=1 tune=zerolatency intra-refresh-true! rtph264pay pt=96 ! udpsink host={} port={}".format(ip,port))
        except ValueError:
            logging.info("Unknown mode")
        print(cmd)
        return cmd

class RemoteViewer:
    OUTPUT = Enum("OUTPUT", "OPENCV WINDOW")

    def get_my_ip(self):
        # a = subprocess.run('ifconfig',capture_output=1) #capture_output is only in python 3.7 and above
        m = None
        try:
            a = subprocess.run('ifconfig', stdout=subprocess.PIPE).stdout.strip()
            m = re.search( b"192\.168\.1\.[0-9][0-9][0-9]", a)
        except FileNotFoundError:
            a = b"127\.0\.0\.1"

        if m is not None:
            return m.group()
        else:
            print("Can't find my ip on robot network!")
            return None

    def __init__(self, mode = None):
        if mode == None:
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
        self.pub.send({"host": self.remote_host, "cmd": "close", "name":self.camera_name})
        self.pub.send({"host": self.remote_host, "cmd": "close", "name":self.camera_name})
        self.pub.send({"host": self.remote_host, "cmd": "close", "name":self.camera_name})

    def get_free_port(self):
        port = 5001
        while 1:
            try:
                with closing(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as s:
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

        self.pub.send({"ip": self.ip, "host": self.remote_host, "resolution": self.resolution, "port":port, "name":self.camera_name})

        if self.mode == self.OUTPUT.WINDOW:
            # caps="application/x-rtp" is what makes things slow. replaces with gdppay
            cmd = 'gst-launch-1.0 udpsrc port={} caps="application/x-rtp", payload=96 ! rtph264depay ! avdec_h264 ! autovideosink sync=false'.format(port)
            # cmd = 'gst-launch-1.0 udpsrc port={} ! gdpdepay ! rtph264depay ! avdec_h264 ! autovideosink sync=false'.format(port)
            args = shlex.split(cmd)
            # shell = True need to open a window. $DISPLAY needs to be set?
            # print(args)
            # self.process = subprocess.Popen(cmd, shell=True)
            self.process = subprocess.Popen(args)


        elif self.mode == self.OUTPUT.OPENCV:
            arg = 'gst-launch-1.0 udpsrc port={} caps="application/x-rtp", payload=96 ! rtph264depay ! avdec_h264 ! fdsink sync=false'.format(port)
            # cmd = 'gst-launch-1.0 udpsrc port={} ! gdpdepay ! rtph264depay ! avdec_h264 ! fdsink'
            self.process = subprocess.Popen(arg, shell=True, stdout=subprocess.PIPE)

    """def __del__(self):
        self.close()
"""
    def stream(self, hostname, camera_name = None):
        self.remote_host = hostname
        self.camera_name = camera_name
        self.open()

        if self.mode == self.OUTPUT.WINDOW:
            self.monitor(loop = True)

    def read(self):
        # self.monitor(loop= False)
        return self.process.stdout.read(320*240*3)

    def monitor(self, loop = True):
        # TODO FINSHI
        if loop:
            while 1:
                self.process.wait()
                self.process = subprocess.Popen(arg, shell=True, stdout=subprocess.PIPE)
                self.open()

        else:
            if self.process.poll():
                return
            else:
                self.process = subprocess.Popen(arg, shell=True, stdout=subprocess.PIPE)
                self.open()
                # resend request




import argparse
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='subparser')

    server = subparsers.add_parser("server")
    server.add_argument('camera_name', nargs='?', default=None, help="used to disambiguate multiple cameras on one pi")

    viewer = subparsers.add_parser("viewer")
    viewer.add_argument('hostname', help="hostname of the computer we want to view")
    viewer.add_argument('camera_name', nargs='?', default=None, help="used to disambiguate multiple cameras on one pi")

    args = parser.parse_args()

    if args.subparser == 'viewer':
        r = RemoteViewer()
        r.stream(args.hostname, args.camera_name)

    elif args.subparser == 'server':
        s = Server(args.camera_name)
        s.listen()
