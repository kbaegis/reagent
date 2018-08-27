#!/bin/bash

function SIGNAL() {
	printf "Signal caught. Doing nothing.\n"
}

sed -i "s#^recursor=.*#recursor=$RECURSOR#g" /etc/powerdns/pdns.conf
pdns_server
sleep 5
PID=$!
trap SIGNAL SIGTERM
wait $PID
