plamp
=====

plamps are good


machine setup
===========

Raspberry PI packages

* apt-get install -y python-dev python-pip python-bluez avahi-daemon
* pip install Flask
* pip install -U flask-cors
* pip install requests
* pip install gevent-socketio

Install the LED driver software
===============

sudo apt-get install -y build-essential git scons swig

git clone https://github.com/jgarff/rpi_ws281x.git
cd rpi_ws281x
scons

cd python && sudo python setup.py install


Install the plamp service
====================

Then run install.bash as root from this directory


