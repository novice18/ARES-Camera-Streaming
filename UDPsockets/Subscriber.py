import socket
import msgpack
from time import monotonic

MAX_SIZE = 65507
REQUEST_PORT = 5000


class Subscriber:
    def __init__(self, port, timeout=0.2):
        """ Create a Subscriber Object
        Arguments:
            port         -- the port to listen to messages on
            timeout      -- how long to wait before a message
                            is considered out of date
        """

        self.max_size = MAX_SIZE

        self.port = port
        self.timeout = timeout

        self.last_data = None
        self.last_time = float('-inf')

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)    # UDP
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

        self.sock.settimeout(timeout)
        self.sock.bind(("", port))

    def recv(self):
        """
        Receive a single message from the socket buffer.
        It blocks for up to timeout seconds.
        If no message is received before timeout it raises a timeout exception.
        """

        try:
            self.last_data, address = self.sock.recvfrom(self.max_size)
        except BlockingIOError:
            raise socket.timeout(
                "No messages in buffer and called with timeout = 0")

        self.last_time = monotonic()
        return msgpack.loads(self.last_data)

    def get(self):
        """
        Returns the latest message it can without blocking.
        If the latest massage is older then timeout seconds,
        it raises a timeout exception.
        """
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
            return msgpack.loads(self.last_data)
        else:
            raise socket.timeout("timeout=" + str(self.timeout) +
                                 ", last message time=" + str(self.last_time) +
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
