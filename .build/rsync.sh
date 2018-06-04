#!/bin/bash

#Replace values as needed

RSYNC_PASSWORD='<changeme>' rsync --chmod 775 -rv /usr/portage/packages/generic/ nobody@<BINHOST>::packages --exclude Packages
RSYNC_PASSWORD='<changeme>' rsync --chmod 775 -rv /usr/portage/distfiles/ nobody@<BINHOST>::distfiles
