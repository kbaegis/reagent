#!/bin/bash

#UID=$(id -u)
GID=$(id -g)
DATE=$(date "+%d-%m-%y")
REPO="/opt/oci/"
SPECPATH=/var/tmp/catalyst/builds/default
INITIAL=($(realpath --relative-to=$REPO $REPO/*.*.buildah))
THREADS=$(($(nproc) + 1))
STAGE3TAR="$REPO/.stages/stage3-amd64-hardened-latest.tar.bz2"
STAGE3URL="https://crucible.lab/distfiles/stage3-amd64-hardened-latest.tar.bz2"
REGISTRY="crucible.lab:4000/oci"
INITIAL_XFAIL=1
TIMEFORMAT='%E seconds'
red=$(tput setaf 1)
yellow=$(tput setaf 190)
gold=$(tput setaf 3)
normal=$(tput sgr0)
blue=$(tput setaf 6)
trap '' 2

usage() {
#Returns help
  printf '%s\n' "usage: $0 [-p | --portage] [-c | --catalyst] [-i | --initial] [-b | --build '<images>'|'all'] [-e | --everything] [-h | --help] [-d | --debug]" 1>&2
  exit 0
}

arguments() {
#function parses arguments
  OPTS=$(getopt -n $0 -s bash -o dpechib: --long debug,everything,portage,catalyst,help,initial,build: -- "$@")
  if [ $# = 0 ]
  then 
    usage
    exit 0
  fi
  while true
  do
    case "$1" in
      -i | --initial ) export BUILD_INITIAL=true;shift;;
      -b | --build ) export BUILD_IMAGES+=($2);shift;shift;;
      -c | --catalyst ) export CATALYST=true;shift;;
      -p | --portage ) export PORTAGE_BUILD=true;shift;;
      -e | --everything ) export CATALYST=true;export PORTAGE_BUILD=true;export BUILD_INITIAL=true;export BUILD_IMAGES+=(all);shift;;
      -d | --debug ) set -x;shift;;
      -h | --help ) usage; break;;
      -- ) shift; break;;
      * ) break;;
    esac
  done
}

catalyst() {
n=0;trap "cleanup catalyst" 2
#Function runs catalyst for gentoo stage1-3;generates catalyst-cache containing all the cached builds from the previous run. This will take a long time the first time you run it.
  if [[ "$CATALYST" == "true" ]]
  then
    emaint -a all 1>/dev/null
    export CATALYSTCACHE=$(sudo buildah from $REGISTRY/catalyst-cache:latest)
    export CATALYSTCACHEMNT=$(sudo buildah mount $CATALYSTCACHE)
    rsync -arv $CATALYSTCACHEMNT/ /var/tmp/catalyst/packages/
    if [[ ! -e /var/tmp/catalyst/builds/hardened/stage3-amd64-hardened-latest.tar.bz2 ]]
    then
      mkdir -p /var/tmp/catalyst/builds/hardened/
      mkdir -p /usr/portage/distfiles/
      curl $STAGE3URL -o /var/tmp/catalyst/builds/hardened/stage3-amd64-hardened-latest.tar.bz2||exit 1
    fi
    TIMEFORMAT="${blue}Catalyst took %E seconds to snapshot.${normal}"
    time (sudo EPYTHON="python3.5" catalyst -s latest) 2> >(tee -a ${REPO}/build.log)
    for i in $(ls $SPECPATH/*.spec)
    do
      printf '%s\n' "${gold}$Building $i.${normal}"|tee -a $REPO/build.log
      TIMEFORMAT="${blue}Catalyst took %E seconds to build.${normal}"
      time (sudo EPYTHON="python3.5" catalyst -f $i) 2> >(tee -a $REPO/build.log)||exit 1
    done && \
    rsync -r /var/tmp/catalyst/packages/hardened/ $CATALYSTCACHEMNT && \
    sudo buildah umount $CATALYSTCACHE && \
    sudo buildah commit --format oci --rm --squash $CATALYSTCACHE $REGISTRY/catalyst-cache:$DATE && \
    sudo buildah tag $REGISTRY/catalyst-cache:$DATE $REGISTRY/catalyst-cache:latest && \
    export PUSH+=("$REGISTRY/catalyst-cache:$DATE" "$REGISTRY/catalyst-cache:latest")
  fi
}

bud_build() {
n=0;trap "cleanup bud_build" 2
TIMEFORMAT="${blue}$2 took %E seconds to build.${normal}"
#$1=dockerfile, $2 is image name, $3 is path and additional arguments
  if time (sudo buildah bud --build-arg GHEAD="$(git -C $REPO rev-parse HEAD)" --build-arg BDATE="$(date --rfc-3339=date)" -v "$PORTAGEMNT:/usr/portage/" -f $1 -t $REGISTRY/$2:latest -t "$REGISTRY/$2:$DATE" $3) 2> >(tee -a $REPO/build.log)
  then
    export PUSH+=("$REGISTRY/$2:latest" "$REGISTRY/$2:$DATE")
  else
    export FAILED+=("$1")
  fi
  return 0
}

registry-push() {
n=0;trap "cleanup registry-push" 2
# Pushes images from PUSH() array
# buildah push -f v2s2 $REGISTRY/$1:$DATE docker://$REGISTRY/$1:latest
# buildah push -f v2s2 $REGSITRY/$1:$DATE docker://$REGSITRY/$1:$DATE
  export PUSH
  for image in ${PUSH[@]}
  do
    printf '%s\n' "${yellow}Pushing $image.${normal}"|tee -a $REPO/build.log
    TIMEFORMAT="${blue}Image took %E seconds to push.${normal}"
    time (sudo buildah push -f v2s2 $image docker://$image) 2> >(tee -a ${REPO}/build.log)
  done
  export FAILED
}

portage-sync() {
n=0;trap "cleanup portage-sync" 2
  export PORTAGE=$(sudo buildah from $REGISTRY/portagedir:latest)
  export PORTAGEMNT=$(sudo buildah mount $PORTAGE)
  if [[ "$PORTAGE_BUILD" == "true" ]]
  then
    TIMEFORMAT="${blue}Updating portage took %E seconds.${normal}"
    time (
      PORTDIR="$PORTAGEMNT" emaint -a sync 1>/dev/null
      sudo buildah commit --format oci --rm --squash $PORTAGE $REGISTRY/portagedir:$DATE && \
      sudo buildah tag $REGISTRY/portagedir:$DATE $REGISTRY/portagedir:latest
      export PUSH+=("$REGISTRY/portagedir:$DATE" "$REGISTRY/portagedir:latest")
      buildah rm $PORTAGE
      export PORTAGE=$(sudo buildah from $REGISTRY/portagedir:latest)
      export PORTAGEMNT=$(sudo buildah mount $PORTAGE)
    )
  fi
}

bootstrap() {
n=0;trap "cleanup bootstrap" 2
TIMEFORMAT="${blue}Bootstrap function took %E seconds.${normal}"
# function creates a gentoo-stage3-amd64-hardened container using host/parent container utilities
  rsync -r /var/tmp/catalyst/builds/hardened/ $REPO/.stages/ 2>/dev/null
  if [[ "${BUILD_INITIAL}" == "true" && -e $STAGE3TAR ]]
  then
    time (
      printf '%s\n' "${gold}Bootstrapping via stage3.${normal}"|tee -a $REPO/build.log 
      local STAGE3=$(sudo buildah from scratch)
      local STAGE3MNT=$(sudo buildah mount $STAGE3)
#     sudo rsync --chown=$UID:$GID -acv /var/tmp/catalyst/builds/hardened/ $REPO/.stages/||printf "Catalyst builds not found.\n"
      sudo buildah add $STAGE3 $STAGE3TAR /
      sudo buildah run $STAGE3 -- sed -i -e 's/#rc_sys=""/rc_sys="docker"/g' /etc/rc.conf
      sudo buildah run $STAGE3 -- mkdir -p /usr/portage/
      printf 'America/Denver\n'|sudo tee $STAGE3MNT/etc/timezone
      sudo buildah config --cmd /bin/bash --created-by "poseidon" --author "poseidon@nulllabs" --label name=$REGSITRY/gentoo-stage3-amd64-hardened $STAGE3
      sudo buildah umount $STAGE3
      printf '%s\n' "${gold}Committing stage3 image.${normal}"|tee -a $REPO/build.log
      sudo buildah commit --format oci --rm --squash $STAGE3 $REGISTRY/gentoo-stage3-amd64-hardened:$DATE && \
      sudo buildah tag $REGISTRY/gentoo-stage3-amd64-hardened:$DATE $REGISTRY/gentoo-stage3-amd64-hardened:latest && \
      export PUSH+=("$REGISTRY/gentoo-stage3-amd64-hardened:latest" "$REGISTRY/gentoo-stage3-amd64-hardened:$DATE")
    export STAGE3=$(sudo buildah from $REGISTRY/gentoo-stage3-amd64-hardened:latest)
    export STAGE3MNT=$(sudo buildah mount $STAGE3)
    ) 2> >(tee -a $REPO/build.log)
  else
    printf '%s\n' "${gold}Loading portage and stage3 from image.${normal}"|tee -a $REPO/build.log
    export STAGE3=$(sudo buildah from $REGISTRY/gentoo-stage3-amd64-hardened:latest)
    export STAGE3MNT=$(sudo buildah mount $STAGE3)
  fi
}

prune() {
n=0;trap "cleanup prune" 2
  for i in $(sudo buildah containers -q);do sudo buildah rm $i 2>/dev/null;done
  for i in $(sudo buildah images|grep '<none>'|awk '{ print $1 };');do sudo buildah rmi -f $i 2>/dev/null;done
}

initial_images() {
n=0;trap "cleanup initial_images" 2
  if [[ "${BUILD_INITIAL}" == "true" ]]
  then
    INITIAL_ERRORS=0
    for i in ${INITIAL[@]}
    do
      if [[ $INITIAL_ERRORS -gt $INITIAL_XFAIL ]]
      then
        exit 1
      fi
      pathname=$(dirname $i)
      name=$(echo $i|awk -F"[.]" '{ print $2 };')
      printf '%s\n' "${gold}Building $name.${normal}"|tee -a $REPO/build.log
      bud_build "$REPO/$i" $name $pathname || (( ++INITIAL_ERRORS ))
    done
  fi
}

project_images() {
n=0;trap "cleanup project_images" 2
##Images (loop for $REPO/*/*.buildah
  if [[ "${BUILD_IMAGES}" == "all" || "${BUILD_IMAGES}" == "*" ]]
  then
    for i in $(realpath --relative-to=$REPO $REPO/*/*.buildah)
    do
      read a b <<< $(echo $i|tr '/' ' ')
      printf '%s\n' "${gold}Building $a.${normal}"|tee -a $REPO/build.log
      pathname=$REPO/$i/
#     bud_build "$REPO/$i" $a "--squash $pathname"
      bud_build "$REPO/$i" $a "$pathname"
    done
  elif [[ ${BUILD_IMAGES[@]} ]]
  then
    for i in ${BUILD_IMAGES[@]}
    do
      if [ -e $REPO/$i/$i.buildah ]
      then
        printf '%s\n' "${gold}Building $i${normal}"|tee -a $REPO/build.log
        pathname=$REPO/$i/
#       bud_build "$REPO/$i/$i.buildah" $i "--squash $pathname"
        bud_build "$REPO/$i/$i.buildah" $i "$pathname"
      else
        printf '%s\n' "${red}No buildah file found for $i. Skipping.${normal}"|tee -a $REPO/build.log
      fi
    done
  fi
}

cleanup() {
  printf '%s' "${red}Signal caught.${normal} "
  (( ++n >= 3)) && printf '%s\n' "${red}Aborting $0.${normal}"|tee -a $REPO/build.log && exit 1
  (( n >= 2)) && printf '%s\n' "${red}$1 aborted.${normal}"|tee -a $REPO/build.log && (prune&) && return 1
  printf '%s\n' "${red}Press ctrl+c again to abort the function, twice to quit.${normal}"
}

main() {
  BUILD_IMAGES_STRING="${BUILD_IMAGES[@]}"
  printf '%s\n' "${gold}$(if [[ "$CATALYST" == "true" ]];then printf "Catalyst build";else printf "Build";fi) initiated at $(date) with$(if [[ "$BUILD_INITIAL" == "true" ]];then printf " initial images and";fi)$(if [[ ${BUILD_IMAGES[@]} ]];then printf " project images: $BUILD_IMAGES_STRING.";else printf " no project images.";fi) ${normal}"|tee -a $REPO/build.log
  time (
    portage-sync
    catalyst
    bootstrap
    initial_images
    project_images
    registry-push
    prune
    TIMEFORMAT="${blue}$0 took %E seconds to run.${normal}" 
  ) 2> >(tee -a ${REPO}/build.log)
  printf '%s\n' "${gold}Script complete at $(date).${normal}"|tee -a $REPO/build.log
  echo ${PUSH[@]}
  echo ${FAILED[@]}
  if [ ${#PUSH[@]} -gt 0 ]
  then 
    printf "${blue}Success: %s${normal}\n" "${PUSH[@]}"|tee -a $REPO/build.log
  else
    printf "No success to report.\n"
  fi
  if [ ${#FAILED[@]} -gt 0 ]
  then 
    printf "${red}Failure: %s${normal}\n" "${FAILED[@]}"|tee -a $REPO/build.log
  else
    printf "No failure to report.\n"
  fi
}

arguments $@
main && exit 0
exit 1
