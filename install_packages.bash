#!/usr/bin/env bash

# install pimonori
curl -sS get.pimoroni.com/unicornhat | bash

# Using Debian, as root
curl -sL https://deb.nodesource.com/setup_5.x | bash -
apt-get install -y nodejs

apt-get install -y vim ipython lsb-release git
apt-get install -y python-dev python-pip python-bluez avahi-daemon

pip install Flask
pip install -U flask-cors
pip install requests
pip install gevent
pip install gevent-socketio

