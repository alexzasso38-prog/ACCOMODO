-- Local-only credentials, replaced by separate secret-managed roles in production.
CREATE ROLE tavolo_app LOGIN PASSWORD 'local-demo-app' NOSUPERUSER NOBYPASSRLS;
CREATE DATABASE tavolo_demo_test;
