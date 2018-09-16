#!/bin/bash

touch /var/log/charon.log
/usr/sbin/ipsec start --conf $IPSEC_PATH
tail -f /var/log/charon.log
