gst-launch-1.0 udpsrc port=10000 caps="application/x-rtp" ! rtph264depay ! avdec_h264 ! autovideosink sync=false
