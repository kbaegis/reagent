#!/bin/bash

sed -i "s#server = \".*\"#server = \"$DATABASESRV\"#g" /usr/local/etc/raddb/mods-available/sql.postgresql
sed -i "s#\(radius_db.*\)host=[^\ ]*\(.*\)#\1host=$DATABASESRV\2#g" /usr/local/etc/raddb/mods-available/sql.postgresql
radiusd $@
