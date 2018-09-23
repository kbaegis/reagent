#Dockerfile to build the requisite build image used by reagent from scratch and from public repos.
FROM gentoo/stage3-amd64:latest
ENV REGISTRY="crucible.lab:4000" \
  NAMESPACE="/oci/" \
  BUILDAH_TAG="v1.3" \
  GOPATH="/root/.go" \
  GOBIN="/root/.go/bin"
RUN printf 'dev-util/bats ~amd64\napp-emulation/skopeo ~amd64\ndev-util/catalyst ~amd64\ndev-python/snakeoil ~amd64\ndev-python/pydecomp ~amd64\napp-emulation/cri-o ~amd64\nnet-misc/cni-plugins ~amd64\ndev-util/ostree ~amd64\n' >>/etc/portage/package.accept_keywords/global \
 && mkdir -p /etc/portage/env/ \
 && printf 'FEATURES="-usersandbox -sandbox"\n' >> /etc/portage/env/nosandbox.conf \
 && printf 'FEATURES="-usersandbox"\n' >> /etc/portage/env/nousersandbox.conf \
 && printf 'dev-lang/go nousersandbox.conf\ndev-go/go-md2man nosandbox.conf\napp-emulation/skopeo nosandbox.conf\n' >> /etc/portage/package.env \
 && printf 'autocmd BufNewFile,BufRead *.buildah set syntax=dockerfile\n' >> ~/.vimrc \
 && printf "app-emulation/cri-o device-mapper seccomp btrfs ostree\ndev-util/pkgconfig internal-glib\nsys-apps/help2man -nls\n" >>/etc/portage/package.use/build \
 && emaint -a all \
 && emerge --oneshot portage \
 && emerge -DNu world --with-bdeps=y
RUN emerge dev-go/sanitized-anchor-name dev-python/pygpgme dev-libs/libassuan sys-libs/libseccomp app-emulation/skopeo sys-fs/fuse sys-libs/libselinux app-admin/sudo dev-go/go-md2man dev-python/snakeoil dev-util/catalyst dev-libs/glib app-misc/jq net-dns/bind-tools dev-vcs/git
RUN mkdir -p /etc/catalyst/portage/package.use \
 && mkdir -p /etc/catalyst/portage/package.mask \
 && mkdir -p /var/tmp/catalyst/builds/default/ \
 && mkdir -p /var/tmp/catalyst/builds/hardened/ \
 && mkdir -p /usr/portage/distfiles/ \
 && chmod -R 777 /usr/lib/go/pkg/linux_amd64/*
RUN emerge app-emulation/runc \
 && git clone https://github.com/ostreedev/ostree /tmp/ostree-git/ \
 && /tmp/ostree-git/autogen.sh \
 && cd /tmp/ostree-git/ \
 && ./configure \
 && make -j32\
 && make install \
 && ln -s /usr/local/lib64/libostree-1.* /usr/lib64/ \
 && ln -s /usr/local/lib64/pkgconfig/ostree-1.pc /usr/lib64/pkgconfig/
RUN mkdir -p $GOPATH/src/github.com/projectatomic/buildah \
 && git clone https://github.com/projectatomic/buildah $GOPATH/src/github.com/projectatomic/buildah/ \
 && git -C $GOPATH/src/github.com/projectatomic/buildah/ checkout $BUILDAH_TAG \
 && cd $GOPATH/src/github.com/projectatomic/buildah/ \
 && make \
 && make install 
RUN mkdir -p $GOPATH/src/github.com/containers/libpod \
 && git clone https://github.com/containers/libpod/ $GOPATH/src/github.com/containers/libpod/ \
 && cd $GOPATH/src/github.com/containers/libpod/ \
 && make -j32 \
 && make install 
RUN mkdir -p $GOPATH/src/github.com/kubernetes-sigs/cri-o \
 && git clone https://github.com/kubernetes-sigs/cri-o $GOPATH/src/github.com/kubernetes-sigs/cri-o \
 && cd $GOPATH/src/github.com/kubernetes-sigs/cri-o/ \
 && mkdir bin \
 && make bin/conmon -j32
RUN mkdir -p $GOPATH/src/github.com/kubernetes-incubator/cri-o \
 && git clone https://github.com/kubernetes-incubator/cri-o $GOPATH/src/github.com/kubernetes-incubator/cri-o \
 && cd $GOPATH/src/github.com/kubernetes-incubator/cri-o \
 && make install \
 && git clone https://github.com/containernetworking/plugins.git $GOPATH/src/github.com/containernetworking/plugins \
 && cd $GOPATH/src/github.com/containernetworking/plugins \
 && ./build.sh \
 && mkdir -p /usr/libexec/cni \
 && cp bin/* /usr/libexec/cni
RUN git clone https://github.com/kbaegis/reagent.git /opt/oci/ \
 && git -C /opt/oci checkout $GBRANCH \
 && git -C /opt/oci/ submodule init \
 && git -C /opt/oci/ submodule update --recursive --remote --merge \
 && ln -s /opt/oci/pybuild.py /usr/local/bin/build \
 && useradd jenkins -G wheel \
 && printf "%%wheel ALL=(ALL) NOPASSWD: ALL\n" >>/etc/sudoers \
 && mkdir -p /etc/containers/ \
 && printf "[registries.search]\nregistries = ['$REGISTRY', 'docker.io', 'registry.fedoraproject.org', 'registry.access.redhat.com']\n\n[registries.insecure]\nregistries = ['$REGISTRY']\n\n[registries.block]\nregistries = ['docker.io']" >/etc/containers/registries.conf \
 && for i in $(ls /opt/oci/build/bin/*);do ln -s $i /usr/local/bin/;done
ADD catalyst/* /etc/catalyst/
ADD catalyst-portage/* /etc/catalyst/portage/
ADD catalyst-package.use/* /etc/catalyst/portage/package.use/
ADD catalyst-package.mask/* /etc/catalyst/porgage/package.mask/
ADD spec/* /var/tmp/catalyst/builds/default/

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["-vpcib","all"]
