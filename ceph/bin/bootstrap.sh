#!/bin/bash

if [[ "$MASTER" == "$(hostname)" ]]
then
	NODE=$MASTER
	ln -s /etc/ceph/ceph.mon.keyring /etc/ceph/ceph.mon.$NODE.keyring
	monmaptool --create --fsid 8ad364ea-b26e-4870-a580-e93b09eb7d3f --add ceph.mgmt 172.21.255.252 /etc/ceph/ceph.initial-monmap
	monmaptool --add praxis.mgmt 172.21.255.253 /etc/ceph/ceph.initial-monmap
	monmaptool --add tine.mgmt 172.21.0.3 /etc/ceph/ceph.initial-monmap
	ceph-mon --mkfs -i $NODE --monmap /etc/ceph/ceph.initial-monmap --keyring /etc/ceph/ceph.mon.$NODE.keyring --public-addr 172.21.255.252
	ceph-mon -i $NODE -c /etc/ceph/ceph.conf
fi

OSDHOST=$(hostname)
lvmetad
vgscan --mknodes
ceph-volume lvm zap $OSDHOST/ceph
