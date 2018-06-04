#!/bin/bash

/usr/bin/php-fpm --fpm-config /etc/php/fpm-php7.1/php-fpm.conf&
/usr/sbin/nginx -t -c /etc/nginx/nginx.conf
/usr/sbin/nginx -c /etc/nginx/nginx.conf -g 'daemon off;'&
PID=$!
trap 'nginx -s stop' SIGTERM
wait $PID
