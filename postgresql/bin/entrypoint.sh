#!/bin/bash

function SIGNAL() {
	su postgres -c '/bin/env pg_ctl stop'
}

su postgres -c '/usr/bin/postgres -c config_file=/etc/postgresql/postgresql.conf -c hba_file=/etc/postgresql/pg_hba.conf -c ident_file=/etc/postgresql/pg_ident.conf'|tee -a /var/log/postgresql.log&
sleep 5
PID=$!
trap SIGNAL SIGTERM
wait $PID
