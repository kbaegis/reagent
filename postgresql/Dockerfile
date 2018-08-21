FROM crucible.lab:4000/gentoo/libressl:latest
LABEL maintainer="poseidon@poseidon.mgmt" organization="nulllabs" version="$DATE"
ENV PGDATA=/var/lib/postgresql/10/data/

RUN printf 'dev-db/postgresql -kerberos ldap libressl nls pam perl python readline server ssl threads uuid xml zlib\napp-crypt/mit-krb5 keyutils libressl nls openldap pkinit threads' >>/etc/portage/package.use/postgresql \
 && emerge -bg dev-db/postgresql

RUN $HOME/.build/rsync.sh

RUN emerge --config dev-db/postgresql \
 && mkdir /run/postgresql/ \
 && mkdir /etc/ssl/postgresql/ \
 && mkdir /var/tmp/sql/ \
 && echo '' >/var/log/postgresql.log

ADD conf.d/* /etc/conf.d/
ADD postgresql/* /etc/postgresql-10/
ADD bin/* /usr/local/bin/
ADD --chown=postgres:postgres .x509.replication/* /etc/ssl/postgresql/
ADD --chown=postgres:postgres .x509/* /etc/ssl/postgresql/

RUN chown postgres:postgres /run/postgresql/ \
 && chown postgres:postgres /var/log/postgresql.log \
 && chmod 640 /etc/ssl/postgresql/* \
 && chmod 600 /etc/ssl/postgresql/*.key.pem

ADD sql/* /var/tmp/sql/
RUN su postgres -c '/usr/lib64/postgresql-10/bin/pg_ctl -D /var/lib/postgresql/10/data -l /var/log/postgresql.log start' \
 && for i in $(ls /var/tmp/sql/);do psql -U postgres </var/tmp/sql/$i;done  \
 && su postgres -c '/usr/lib64/postgresql-10/bin/pg_ctl -D /var/lib/postgresql/10/data -l /var/log/postgresql.log stop'

EXPOSE 5432/tcp

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

#CMD ["-D","/var/lib/postgresql/10/data","-l","/var/log/pg.log","start"]

HEALTHCHECK --interval=30s --timeout=5s CMD /usr/local/bin/healthcheck.sh
