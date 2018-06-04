# buildah-gentoo

buildah-gentoo (OCI)
--------------

## Build stages

buildah-gentoo is a wrapper for several utilties that allow you to incorporate a full end-to-end build into a container. 

-c --catalyst
Build catalyst stages 1-3 using specfiles and an existing stage3. 

-i --initial
Build all container images in the root directory in the numbered order. Do this for your core image layers. Serveral examples are included [go, java, libressl, stage3, etc]

-b --build (image1 image2 ... imageN)
Build select images

## Design

By leveraging a binhost in conjunction with portage, the only rebuilds that become necessary are those that are necessary for upgrades or changes in useflags. This gives you full control at every step of the build while cutting down on buildtimes dramatically. Additionally, buildah does not snapshot your container storage after every build step. Snapshotting currently only occurs upon commit. If smaller images are necessary, it's strongly recommended to add a script to remove build dependencies. 
###### Project dependencies: 
* bash (ash/sh untested)
* [buildah](https://github.com/projectatomic/buildah)
* private docker registry (optionally secured)
* [Gentoo Binhost](https://wiki.gentoo.org/wiki/Binary_package_guide)
* tls certs (optional, but assumed [https://])

###### Certificates: 
`git submodule add -b <branch> <url> .x509`

