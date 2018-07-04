#!/bin/bash

NODE=$(hostname).mgmt
vgscan --mknodes

#MON
if [ -e /var/lib/ceph/mon/ceph-$(hostname).mgmt ]
then
	ceph-mon -i $(hostname).mgmt -c /etc/ceph/ceph.conf
fi

#MGR
if [ -e /var/lib/ceph/mgr/ceph-$(hostname)/ ]
then 
	ceph-mgr -i $(hostname)
fi

#MDS
if [ -e /var/lib/ceph/mds/ceph-$(hostname)/ ]
then 
	ceph-mds -i $(hostname)	
fi

#OSD
JSON=$(ceph-volume lvm list --format json)
FSID=$(printf "$JSON\n"|tr '.' '_'|jq '.[]|.[].tags.ceph_osd_fsid'|tr -d \")
ID=$(printf "$JSON\n"|tr '.' '_'|jq '.[]|.[].tags.ceph_osd_id'|tr -d \")
ceph-volume lvm activate $ID $FSID
ceph-osd -i $ID -d
