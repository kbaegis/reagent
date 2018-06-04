#!/bin/bash

ps -o pid= $(cat /var/run/nginx.pid) 1>/dev/null||exit 1
curl https://localhost -k 1>/dev/null 2>/dev/null||exit 1
