#!/bin/bash

hosts=(server.home server.lab server.mgmt services.home services.lab services.mgmt praxis.home praxis.lab praxis.mgmt crucible.home crucible.lab crucible.mgmt)
ips=(172.21.255.254 172.22.255.254 172.23.255.254 172.21.255.253 172.22.255.253 172.23.255.253 172.21.255.252 172.22.255.252 172.23.255.252 172.21.255.101 172.22.255.101 172.23.255.101)

failed=()
for target in ${hosts[@]} ${ips[@]};
do
  printf "Target: $target\n"
  dig +retry=0 +time=1 @$target praxis.mgmt 1>/dev/null||(printf "Local query failed.\n" && failed=($failed $target))\
  && dig +retry=0 +time=1 @$target eff.org 1>/dev/null||(printf "Recursive query failed.\n" && failed=($failed $target))\
  && dig +retry=0 +time=1 +dnssec @$target eff.org 1>/dev/null||(printf "DNSSEC failed.\n" && failed=($failed $target))
  curl -s --connect-timeout 1 http://$target 1>/dev/null||(printf "HTTP redirect failed.\n" && failed=($failed $target))
  curl -s --connect-timeout 1 https://$target 1>/dev/null||(printf "HTTPS failed.\n" && failed=($failed $target))
  printf "Failed targets: ${failed[@]}"
done

printf "Failed targets: ${failed[@]}"
