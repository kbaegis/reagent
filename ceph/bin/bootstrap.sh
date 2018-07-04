#!/bin/bash

#rm -r /var/lib/ceph/mon/ceph-$(hostname).mgmt/

##OSD
#OSDHOST=$(hostname)
#lvmetad
#vgscan --mknodes
#ceph-volume lvm zap $OSDHOST/ceph
#ceph-volume lvm prepare --bluestore --data $OSDHOST/ceph
