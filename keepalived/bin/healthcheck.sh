#!/bin/bash

ps -o pid= $(cat /var/run/keepalived.pid)||exit 1
for i in $(awk -F '[/]' '/virtual_ipaddress/{getline; print $1}' /etc/keepalived/keepalived.conf)
do
	ping -c 1 $i||exit 1
done
