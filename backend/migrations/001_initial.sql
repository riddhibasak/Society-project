-- PostgreSQL initial schema. Apply once before starting the API in production.
CREATE TYPE role AS ENUM ('resident','admin');
CREATE TYPE complaintstatus AS ENUM ('open','in_progress','resolved');
CREATE TYPE priority AS ENUM ('low','medium','high');
CREATE TABLE users (id SERIAL PRIMARY KEY, email VARCHAR(255) UNIQUE NOT NULL, name VARCHAR(120) NOT NULL, password_hash VARCHAR(255) NOT NULL, role role NOT NULL DEFAULT 'resident', created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE complaints (id SERIAL PRIMARY KEY, category VARCHAR(80) NOT NULL, title VARCHAR(180) NOT NULL, description TEXT NOT NULL, status complaintstatus NOT NULL DEFAULT 'open', priority priority NOT NULL DEFAULT 'medium', photo_url VARCHAR(500), resident_id INTEGER NOT NULL REFERENCES users(id), created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX ix_complaints_resident_id ON complaints(resident_id); CREATE INDEX ix_complaints_status ON complaints(status); CREATE INDEX ix_complaints_category ON complaints(category);
CREATE TABLE complaint_history (id SERIAL PRIMARY KEY, complaint_id INTEGER NOT NULL REFERENCES complaints(id) ON DELETE CASCADE, actor_id INTEGER NOT NULL REFERENCES users(id), old_status complaintstatus, new_status complaintstatus NOT NULL, note TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX ix_complaint_history_complaint_id ON complaint_history(complaint_id);
CREATE TABLE notices (id SERIAL PRIMARY KEY, title VARCHAR(180) NOT NULL, description TEXT NOT NULL, important BOOLEAN NOT NULL DEFAULT false, author_id INTEGER NOT NULL REFERENCES users(id), created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX ix_notices_important ON notices(important);
CREATE TABLE settings (key VARCHAR(80) PRIMARY KEY, value VARCHAR(255) NOT NULL);
INSERT INTO settings(key,value) VALUES ('overdue_days','3');
