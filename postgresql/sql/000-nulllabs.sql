CREATE USER poseidon SUPERUSER;
CREATE DATABASE poseidon WITH OWNER poseidon;
CREATE USER replication WITH replication;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO replication;
GRANT ALL ON DATABASE poseidon TO replication;
