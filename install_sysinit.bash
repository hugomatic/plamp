#!/bin/bash


# get LED python program


DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo "DIR: ${DIR}"

cat << EOF > plamp.init
#!/bin/bash


### BEGIN INIT INFO
# Provides:          plamp
# Required-Start:    $remote_fs $syslog
# Required-Stop:     $remote_fs $syslog
# Default-Start:     S
# Default-Stop:      0 1 6
# Short-Description: Plamp service
# Description:       Plamps are good
### END INIT INFO

plampdir=$DIR

plamp_proc=plamp_socket.py

plamp_full_path=$plampdir/$plamp_proc

do_start() {
  # Start plamp web server and log to disk
  $plamp_full_path > /tmp/plamp.log 2>&1 &
  return 0
}

do_stop() {
  # killall -9 $plamp_proc
  kill $(ps aux | grep "[p]ython $plamp_full_path" | awk '{print $2}')
}

do_status() {
  echo plamp pid: $(ps aux | grep "[p]ython $plamp_full_path" | awk '{print $2}')  
}

case "$1" in
    start)
  do_start
        ;;
    status)
        do_status
        ;;
    restart|reload|force-reload)
        do_stop
        do_start
        ;;
    stop)
  do_stop
        ;;
    *)
        echo "Usage: $0 start|stop|status" >&2
        exit 3
        ;;
esac

exit 0
EOF


cp $DIR/plamp.init /etc/init.d/plamp

sudo update-rc.d plamp defaults



