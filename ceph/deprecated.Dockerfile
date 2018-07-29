FROM crucible.lab:4000/gentoo/portage:latest
LABEL maintainer="poseidon@poseidon.mgmt"

ARG THREADS=33
ENV THREADS=$THREADS

##Header
RUN $HOME/.build/prep.sh

RUN printf '172.23.255.252 services.lab\n' >>/etc/hosts \
 && export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
 && echo '=sys-cluster/ceph-12.2.2 ~amd64' >/etc/portage/package.accept_keywords \
 && printf 'dev-lang/python sqlite\ndev-libs/boost python context\nsys-cluster/ceph cephfs fuse mgr radosgw ssl' >/etc/portage/package.use/ceph \
 && FEATURES='-usersandbox -sandbox' emerge -bg sys-cluster/ceph \
 && mkdir -p /etc/ceph/ \
 && mkdir -p /var/lib/ceph/mon/ceph-admin/ \
 && mkdir -p /var/log/ceph \
 && mkdir -p /var/lib/ceph/bootstrap-osd/ 

##Cleanup
RUN $HOME/.build/cleanup.sh

ADD etc/* /etc/ceph/

ENTRYPOINT ["/bin/bash"]
