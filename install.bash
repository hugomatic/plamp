#!/bin/bash


if [ $UID != 0 ]; then
  echo "You're not root.  Run this script under sudo."
  exit 1
fi


# get LED python program


DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo "DIR: ${DIR}"

cp $DIR/plamp.init /etc/init.d/plamp

sudo update-rc.d plamp defaults

#
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



