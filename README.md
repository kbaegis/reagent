# buildah-gentoo

buildah-gentoo (OCI)
--------------

###### update buildah:
```
export GOPATH="~/.go/"
cd ~/.go/src/github.com/projectatomic/buildah/
make -j$THREADS
sudo make install
```

###### Certificates: 
`git submodule add -b <branch> <url> .x509`

###### Project dependencies: 
* ~~bash~~
* python3 (pybuild.py) - Refactored build script into python3
* [buildah](https://github.com/projectatomic/buildah)
* private docker registry (optionally secured)
* [Gentoo Binhost](https://wiki.gentoo.org/wiki/Binary_package_guide)
* tls certs (optional, but assumed [https://])

## Build stages

buildah-gentoo is a wrapper for several utilties that allow you to incorporate a full end-to-end build into a container. 

-c --catalyst
Build catalyst stages 1-3 using specfiles and an existing stage3. 

-i --initial
Build all container images in the root directory in the numbered order. Do this for your core image layers. Serveral examples are included [go, java, libressl, stage3, etc]

-b --build (image1 image2 ... imageN)
Build select images

## Batteries not included

Currently missing from this public repo:

/.x509 and /.build directories

The .build directory includes:

rsync.sh - a script to push built packages from /usr/portage/packages/generic/ to a binary host/webserver

finalize.sh - a script to run emerge --depclean --with-bdeps=n and minimize the size of the leaf images

The .x509 directory is essentially a submodule that points to a private git repo with signing keys and files necessary for internal auth. Those obviously shouldn't be included in a public repo. :)

## Design

By leveraging a binhost in conjunction with portage, the only rebuilds that become necessary are those that are necessary for upgrades or changes in useflags. This gives you full control at every step of the build while cutting down on buildtimes dramatically. Additionally, buildah does not snapshot your container storage after every build step. Snapshotting currently only occurs upon commit. If smaller images are necessary, it's strongly recommended to add a script to remove build dependencies. 

###### Operators note:
This script is heavily tested for existing gentoo systems. Right now it is recommended that you run this in docker with interactive mode, however an entrypoint calling build.sh with the appropriate CMD arguments should work fine for pipelines. Bash is available for exec. 
