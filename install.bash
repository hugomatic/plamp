#!/bin/bash


if [ $UID != 0 ]; then
  echo "You're not root.  Run this script under sudo."
  exit 1
fi


#
# Packages

# apt-get install -y python-pip
# pip install Flask
# pip install -U flask-cors

# get LED python program


DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo "DIR: ${DIR}"

cp $DIR/plamp.init /etc/init.d/plamp

sudo update-rc.d plamp defaults

#
# disable power mgnt on wifi with a conf file
cat << EOF > /etc/modprobe.d/8192cu.conf 

# Disable power management
options 8192cu rtw_power_mgnt=0 rtw_enusbss=0 rtw_ips_mode=1

EOF

####

# plamp_path="/home/pi/plamp"
#
# Add a cron job to keep wifi alive
# line="*/2 * * * * $plamp_path/check_plamp.bash"
# (crontab -u root -l; echo "$line" ) | crontab -u root -



