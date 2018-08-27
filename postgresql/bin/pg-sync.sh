#!/bin/bash

export PGSSLMODE=verify-ca
export PGSSLROOTCERT=/etc/ssl/postgresql/CA.cert.pem
export PGSSLCERT=/etc/ssl/postgresql/libpq-replication.cert.pem
export PGSSLKEY=/etc/ssl/postgresql/libpq-replication.key.pem
pg_basebackup -h services.mgmt -D /var/lib/postgresql/10/main/ -P -U replication --wal-method=stream
