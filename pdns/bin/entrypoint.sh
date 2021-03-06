#!/bin/bash

function SIGNAL() {
	printf "Signal caught. Exiting.\n"
	kill $RPID
	pdns_control quit
}

sed -i "s#^recursor=.*#recursor=$RECURSOR#g" /etc/powerdns/pdns.conf
pdns_server --daemon=yes
SPID=$!
sleep 5
pdns_recursor --daemon=no
RPID=$!
trap SIGNAL SIGTERM
wait $SPID
