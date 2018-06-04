#!/bin/bash

<<<<<<< HEAD
RSYNC_PASSWORD='<changeme>' rsync --chmod 775 -rv /usr/portage/packages/generic/ nobody@<BINHOST>::packages --exclude Packages
RSYNC_PASSWORD='<changeme>' rsync --chmod 775 -rv /usr/portage/distfiles/ nobody@<BINHOST>::distfiles
=======
RSYNC_PASSWORD='syncuser' rsync --chmod 775 -rv /usr/portage/packages/generic/ nobody@crucible.mgmt::docker-packages --exclude Packages
RSYNC_PASSWORD='syncuser' rsync --chmod 775 -rv /usr/portage/distfiles/ nobody@crucible.mgmt::docker-distfiles
>>>>>>> bbb0723... Added template files
emerge --depclean --with-bdeps=n
#emerge --depclean
