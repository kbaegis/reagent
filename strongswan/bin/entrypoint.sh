#!/bin/bash

touch /var/log/charon.log
/usr/sbin/ipsec start
tail -f /var/log/charon.log
