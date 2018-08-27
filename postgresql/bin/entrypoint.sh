#!/bin/bash

function SIGNAL() {
	su postgres -c '/bin/env pg_ctl stop'
}

su postgres -c '/usr/bin/postgres'|tee -a /var/log/postgresql.log&
sleep 5
PID=$!
trap SIGNAL SIGTERM
wait $PID
