# The reagent project - Gentoo containers from scratch

--------------

## Philosophy

The goal of this project was to create an end-to-end build utility that had no proprietary dependencies or opaque source providers residing in dubious legal jurisdictions. Gentoo stage3 files can be produced by catalyst from scratch bootstrapping a core linux environment without traditional package management systems, and further allows for full customization of all your build toolchains and configuration options. 

Libpod/buildah and runc should be provided by the build environment which allow you to run all of reagent's components directly inside a container. 

The eventual goal of this project will be to build a helm chart so that all of the components are parameterized and spun up on a k8s cluster, and images can be discovered and tracked inside jenkins. 

###### Project dependencies: 
* python3
* [buildah](https://github.com/projectatomic/buildah)
* private docker registry (Not required, but presumably you'd want some sort of artifact repo)
* [Gentoo Binhost](https://wiki.gentoo.org/wiki/Binary_package_guide) (not required, but strongly recommended)
* tls certs (optional, but assumed [https://])

## Commands:

Reagent acts as wrapper for several utilties that allow you to incorporate a full end-to-end build into a container.

```
usage: build [-h] [-v] [-p] [-c] [-i] [-b BUILD_TARGETS [BUILD_TARGETS ...]]
             [-t] [-T] [-R]

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         Show verbose output from subprocess commands.
  -p, --portage         Regenerate a container with synced portage contents.
  -c, --catalyst        Build contents of .stages/default/ with catalyst using
                        specfiles.
  -i, --initial         Build all numbered buildah files in the root directory
                        in order with buildah.
  -b BUILD_TARGETS [BUILD_TARGETS ...], --build BUILD_TARGETS [BUILD_TARGETS ...]
                        Build selected contents matched by regex. Use 'all' to
                        build all leaf containers.
  -t, --test            Test images using OCIv1.config.Labels instruction
                        before pushing them to registry.
  -T, --vulnerability   Run vulnerability tests against images.
  -R, --disable-registry
                        Disable push to registry and cleanup.
  --bootstrap           Bootstrap reagent.
```

## Bootstrapping and Getting Started

From the root directory of this repository, run: `docker build -f .bootstrap/build.Dockerfile ./build/` The build container itself may need to be run as a privileged container: `docker run -it --name build-tmp --privileged --rm --entrypoint=/bin/bash <container tag from previous step>`

## Design:

By leveraging a binhost in conjunction with portage, the only rebuilds that become necessary are those that are necessary for upgrades or changes in useflags. This gives you full control at every step of the build while cutting down on buildtimes dramatically. Additionally, buildah does not snapshot your container storage after every build step. Snapshotting currently only occurs upon commit. If smaller images are necessary, it's strongly recommended to add a script to remove build dependencies. 

###### Certificates: 
`git submodule add -b <branch> <url> .x509`
