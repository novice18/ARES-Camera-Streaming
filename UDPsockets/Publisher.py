import socket
import msgpack

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

        self.sock.settimeout(0.2)
        self.sock.connect((self.broadcast_ip, port))

        self.port = port

    def send(self, obj):
        """
        Publish a message.
        The obj can be any nesting of standard python types.
        """

        msg = msgpack.dumps(obj, use_bin_type=False)
        assert len(msg) < MAX_SIZE, "Encoded message too big!"
        self.sock.send(msg)

    def __del__(self):
        self.sock.close()
