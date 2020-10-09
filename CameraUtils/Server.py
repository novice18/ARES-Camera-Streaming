import subprocess
from enum import Enum
import time
import cv2
import imutils
from UDPsockets.Subscriber import Subscriber, REQUEST_PORT
from ProcessMonitor import ProcessMonitor
import logging

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)


class Server:
    INPUT = Enum("INPUT", "RPI_CAM USB_CAM OPENCV USB_H264")

    def __init__(self, name=None, device=None):
        if device is not None:
            device = "/dev/video0"

        self.mode = self.INPUT.USB_CAM
        self.name = name
        self.device = device

        self.sub = Subscriber(REQUEST_PORT, timeout=0)
        self.hostname = subprocess.run(
            'hostname', stdout=subprocess.PIPE).stdout.strip().decode("utf-8")

        self.process = ProcessMonitor()

    def parse_messages(self):
        messages = self.sub.get_list()
        for msg in messages:
            if msg['host'] == self.hostname:
                if msg.get('name') != self.name:
                    continue
                logging.info("got ", msg)
                if msg.get('cmd') == 'close':
                    self.process.stop()
                else:
                    # sleep is necessary to not race ahead of viewer
                    time.sleep(1)
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

        # resolution needs to match with video
        img = imutils.resize(img, width=320)
        self.process.process.stdin.write(
            cv2.cvtColor(img, cv2.COLOR_BGR2YUV_I420))

    def get_cmd(self, msg):
        port, ip = msg["port"], msg["ip"]

        """
        I think this might also give a low latency stream,
        haven't tried it tho:
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
            cmd = ("gst-launch-1.0 v4l2src device={} ! video/x-raw,width=640,height=480 ".format(self.device) +
                   "! x264enc bitrate=100000 speed-preset=1 tune=zerolatency intra-refresh-true! rtph264pay pt=96 ! udpsink host={} port={}".format(ip, port))
        except ValueError:
            logging.info("Unknown mode")
        print(cmd)
        return cmd
