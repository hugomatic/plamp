#!/usr/bin/env bash

# install pimonori
curl -sS get.pimoroni.com/unicornhat | bash

apt-get install -y vim ipython python-dev python-pip python-bluez avahi-daemon
pip install Flask
pip install -U flask-cors
pip install requests
pip install gevent
pip install gevent-socketio

