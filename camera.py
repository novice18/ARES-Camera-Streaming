import socket
import argparse
from CameraUtils.Server import Server
from CameraUtils.RemoteViewer import RemoteViewer
# from collections import namedtuple

timeout = socket.timeout

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='subparser')

    server = subparsers.add_parser("server")
    server.add_argument('camera_name',
                        nargs='?',
                        default=None,
                        help="used to disambiguate multiple cameras on one pi")

    viewer = subparsers.add_parser("viewer")
    viewer.add_argument('hostname',
                        help="hostname of the computer we want to view")
    viewer.add_argument('camera_name',
                        nargs='?',
                        default=None,
                        help="used to disambiguate multiple cameras on one pi")

    args = parser.parse_args()

    if args.subparser == 'viewer':
        r = RemoteViewer()
        r.stream(args.hostname, args.camera_name)

    elif args.subparser == 'server':
        s = Server(args.camera_name)
        s.listen()
