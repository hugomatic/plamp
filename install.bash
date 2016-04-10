#!/usr/bin/env bash


if [ $UID != 0 ]; then
  echo "You're not root.  Run this script under sudo."
  exit 1
fi


apt-get install -y vim ipython python-dev python-pip python-bluez avahi-daemon
pip install Flask
pip install -U flask-cors
pip install requests
pip install gevent
pip install gevent-socketio

# install pimonori
curl -sS get.pimoroni.com/unicornhat | bash



DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo "DIR: ${DIR}"

# systemd
. $DIR/install_plamp_service.bash

# sysinit
#. $DIR/install_sysinit.bash plamp.init

# set the name to plamp.local
# write /etc/hostname and /etc/hosts

cat << EOF > /etc/hostname 
plamp
EOF

cat << EOF > /etc/hosts 
127.0.0.1       localhost
::1             localhost ip6-localhost ip6-loopback
fe00::0         ip6-localnet
ff00::0         ip6-mcastprefix
ff02::1         ip6-allnodes
ff02::2         ip6-allrouters

127.0.1.1       plamp
EOF

if grep BCM2709 /proc/cpuinfo; then
  echo RPI 3
else
  echo not RPI 3
 # disable power mgnt on wifi with a conf file
cat << EOF > /etc/modprobe.d/8192cu.conf 
## Disable power management
options 8192cu rtw_power_mgnt=0 rtw_enusbss=0 rtw_ips_mode=1
EOF
 
fi

####

# plamp_path="/home/pi/plamp"
#
# Add a cron job to keep wifi alive
# line="*/2 * * * * $plamp_path/check_plamp.bash"
# (crontab -u root -l; echo "$line" ) | crontab -u root -



