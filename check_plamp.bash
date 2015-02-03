#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"


mkdir -p $DIR/logs
log="$DIR/logs/plamp_check.log"

if /usr/bin/pgrep -lf app.py ; then
   echo `date` " plamp server up" >> $log
else
   echo `date` " plamp server down" >> $log
   service plamp start
fi

if /sbin/ifconfig wlan0 | grep -q "inet addr:" ; then
  echo `date` " WIFI up" >> $log
else
  echo `date` " WIFI down!" >> $log
  /sbin/ifup --force wlan0

  if /sbin/ifconfig wlan0 | grep -q "inet addr:" ; then
    echo `date` " WIFI repaired" >> $log  
  else
    echo `date` " WIFI still down" >> $log   
  fi  
fi

