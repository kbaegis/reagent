#!/bin/bash

CMD="$(buildah inspect crucible.lab:4000/oci/$1:latest|jq -r '.OCIv1.config.Labels."nulllabs.cri.cmd.test"')"
printf "running command: $CMD\n"
exec $CMD && exit 0
exit 1
