#!/bin/bash

git -C /opt/oci/ pull
git -C /opt/oci/ submodule update --init --recursive
git -C $GOPATH/src/github.com/projectatomic/buildah/ pull
#curl https://patch-diff.githubusercontent.com/raw/projectatomic/buildah/pull/714.patch |git -C $GOPATH/src/github.com/projectatomic/buildah/ am
cd $GOPATH/src/github.com/projectatomic/buildah/ && make && make install
podman login -u build-ci -p $(cat ~/.ssh/.registry.passwd) crucible.lab:4000
/opt/oci/test.py $@
