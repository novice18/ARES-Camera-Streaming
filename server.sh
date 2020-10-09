#! /bin/bash
gst-launch-1.0 -v v4l2src device=/dev/video0 ! "video/x-raw, width=640, height=480" ! videoconvert ! x264enc bitrate=1000000 speed-preset=1 tune=zerolatency ! rtph264pay pt=96 ! udpsink host=127.0.0.1 port=10000
