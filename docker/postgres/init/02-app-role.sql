-- Non-superuser application role for RLS enforcement.
-- Migrations run as agente10 (superuser); application connections use agente10_app.
CREATE ROLE agente10_app LOGIN PASSWORD 'agente10_dev' NOSUPERUSER NOBYPASSRLS;

GRANT USAGE ON SCHEMA public TO agente10_app;
GRANT ALL ON ALL TABLES IN SCHEMA public TO agente10_app;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO agente10_app;

-- Future tables created by agente10 (in migrations) also accessible by agente10_app
ALTER DEFAULT PRIVILEGES FOR ROLE agente10 IN SCHEMA public
    GRANT ALL ON TABLES TO agente10_app;
ALTER DEFAULT PRIVILEGES FOR ROLE agente10 IN SCHEMA public
    GRANT ALL ON SEQUENCES TO agente10_app;
