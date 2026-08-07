-- Create the role + database AREA-303 expects on a local PostgreSQL install.
--
-- Run once, as a superuser (the `postgres` account):
--   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -h localhost -p 5432 -U postgres -f scripts\bootstrap_local_db.sql
--
-- Credentials match the defaults in app/core/config.py, so backend/.env only
-- needs POSTGRES_PORT (already set to 5432). Change the password here and in
-- .env together if you want something else.
--
-- Idempotent: safe to run twice. `CREATE DATABASE` cannot run inside a DO block
-- or a transaction, so the role is guarded and the database is left to error
-- harmlessly with "already exists" on a second run.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'area303') THEN
        CREATE ROLE area303 LOGIN PASSWORD 'area303';
        RAISE NOTICE 'role area303 created';
    ELSE
        RAISE NOTICE 'role area303 already exists — leaving it alone';
    END IF;
END
$$;

-- Owned by area303 so alembic can create tables without extra grants.
CREATE DATABASE area303 OWNER area303 ENCODING 'UTF8';
