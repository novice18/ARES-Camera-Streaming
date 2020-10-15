import subprocess
import os
import signal
import time
import logging

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)


class ProcessMonitor:
    def __init__(self):
        self.process = None
        self.cmd = None

    def start(self, cmd):
        self.cmd = cmd
        if(self.process is not None):
            self.stop()

        # setting preexec_fn=os.setsid allows us to
        # kill the process group allowing for shell=True.
        # without it calling process.terminate() would only
        # kill the shell and not the underlying process
        self.process = subprocess.Popen(self.cmd,
                                        shell=True,
                                        stdin=subprocess.PIPE,
                                        preexec_fn=os.setsid)

        self.monitor()

    def monitor(self):
        try:
            while self.running():
                time.sleep(0.1)

        except KeyboardInterrupt:
            os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            self.process.terminate()
            logging.info("Terminated gstreamer process")

    def stop(self):
        if self.process is not None:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            time.sleep(1)
            while self.running():
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
        self.process = None

    def restart(self):
        self.start(self.cmd)

    def running(self):
        return self.process.poll() is None
