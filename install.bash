#! /bin/sh

sudo cp plamp.init /etc/init.d/plamp
cd /etc/rc2.d
sudo ln -sf ../init.d/plamp S99plamp
