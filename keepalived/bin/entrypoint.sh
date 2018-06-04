#!/bin/bash
rm -rf /var/run/keepalived.pid
rm -rf /var/lock/conntrack.lock
conntrackd -d
/usr/sbin/keepalived -d -D -S 7 -f /etc/keepalived/keepalived.conf --dont-fork --log-console
