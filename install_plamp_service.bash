#!/usr/bin/env bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

cp $DIR/plamp.service /etc/systemd/system

systemctl enable plamp.service
service start plamp
