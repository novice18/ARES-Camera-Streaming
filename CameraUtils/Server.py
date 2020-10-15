import subprocess
import time
from UDPsockets.Subscriber import Subscriber, REQUEST_PORT
from CameraUtils.ProcessMonitor import ProcessMonitor
import logging

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)


class Server:
    def __init__(self, name=None, device=None):
        # TODO: make this dynamic. Maybe extract it from
        # commandline output of camera devices available
        if device is None:
            device = "/dev/video0"

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
                logging.info("Viewer host: {}".format(msg))
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

    def get_cmd(self, msg):
        port, ip = msg["port"], msg["ip"]

        """
        P.S. I haven't calculated the exact latency in ms.
        However, I don't see any visible latency.
        Caveat: It takes around a second or two for the
        viewer's window to pop up.
        """
        try:
            cmd = ('gst-launch-1.0 v4l2src device={} '.format(self.device) +
                   '! videoconvert ! ' +
                   '"video/x-raw,width=640,height=480" ' +
                   '! tee name="ares" ! queue ' +
                   '! autovideosink ares. ! queue ' +
                   '! x264enc interlaced=true qp-min=18 ' +
                   'speed-preset=1 tune=zerolatency ' +
                   '! h264parse ! queue ' +
                   '! rtph264pay pt=96 ' +
                   '! udpsink host={} port={}'.format(ip, port))

        except ValueError:
            logging.error("The program received a ValueError from get_cmd().")

        return cmd
