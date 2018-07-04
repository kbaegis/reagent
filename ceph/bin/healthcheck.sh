#!/bin/bash

OSDSOCKET=$(ls /var/run/ceph/|awk -F '[.-]' '/osd\../{print $2"."$3}')
OSDSTATUS=$(ceph daemon $OSDSOCKET status|jq '.state')
MONSOCKET=$(ls /var/run/ceph/|awk -F '[.-]' '/mon\../{print $2"."$3"."$4}')
MONSTATUS=$(ceph daemon $MONSOCKET mon_status|jq '.state')

if [ $OSDSOCKET ]
then
	if [ "$OSDSTATUS" != '"active"' ]
	then
		exit 1
	fi
fi
if [ $MONSOCKET ]
then
	if [ "$MONSTATUS" != '"leader"' ] && [ "$MONSTATUS" != '"peon"' ]
	then
		exit 1
	fi
fi
