#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"


mkdir -p $DIR/logs
log="$DIR/logs/plamp_check.log"

if ifconfig wlan0 | grep -q "inet addr:" ; then
  echo `date` " WIFI up"
else
  echo `date` " WIFI down!" >> $log
fi

