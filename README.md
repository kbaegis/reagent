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
* python3 (pybuild.py) - Refactored build process
* [buildah](https://github.com/projectatomic/buildah)
* private docker registry (optionally secured)
* [Gentoo Binhost](https://wiki.gentoo.org/wiki/Binary_package_guide)
* tls certs (optional, but assumed [https://])

## Build stages

buildah-gentoo is a wrapper for several utilties that allow you to incorporate a full end-to-end build into a container.

-v --verbose
Print the output from the build commands to the terminal. Even if verbose is not enabled, the file build.log should contain the full output and should be used if something breaks.

-p --portage
Build a container with the contents of /usr/portage/

-c --catalyst
Build catalyst stages 1-3 using specfiles and an existing stage3. A variable defined in pybuild.py determines where it looks for this.

-i --initial
Build all container images in the root directory in the numbered order. Do this for your core image layers. Serveral examples are included [go, java, libressl, stage3, etc]

-b --build (image1 image2 ... imageN)
Build select images matching regular expressions. ** Note - '*' and 'all' are converted to the regular expression '.*', so -b all will select all non-initial images, where -b a+.* will build anything with the first letter 'a'.

## Batteries not included

It's strongly recommended to secure your infrastructure with certificates. I don't create those for you, but they can be added simply in a git submodule to the .x509 directory.

## Design

By leveraging a binhost in conjunction with portage, the only rebuilds that become necessary are those that are necessary for upgrades or changes in useflags. This gives you full control at every step of the build while cutting down on buildtimes dramatically. Additionally, buildah does not snapshot your container storage after every build step. Snapshotting currently only occurs upon commit. If smaller images are necessary, it's strongly recommended to add a script to remove build dependencies. 
