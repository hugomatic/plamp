#!/usr/bin/env bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# generate a service file in the current directory,
# referencing the plamp server in the current directory

cat << EOF > $DIR/plamp.service 

[Unit]
Description=Plamps are good!
DefaultDependencies=no
Before=shutdown.target reboot.target halt.target


[Service]
Type=simple
ExecStart=$DIR/plamp_socket.py

[Install]
WantedBy=multi-user.target

EOF

# send the service file to systemd
cp $DIR/plamp.service /etc/systemd/system

# enable and start the service
systemctl enable plamp.service
service start plamp
