#!/bin/bash

su postgres -c 'PGDATA=/var/lib/postgresql/10/data/ pg_ctl status'
