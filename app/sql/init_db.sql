-- app/sql/init_db.sql
CREATE TABLE IF NOT EXISTS media (
    id SERIAL PRIMARY KEY,
    gdrive JSONB NOT NULL DEFAULT '{"id": "", "path": "", "url": "", "uploaded": false, "verified": false}'::jsonb,
    s3 JSONB NOT NULL DEFAULT '{"id": "", "path": "", "url": "", "uploaded": false, "verified": false}'::jsonb,
    name TEXT NOT NULL,
    uuid TEXT UNIQUE NOT NULL,
    size BIGINT NOT NULL,
    length REAL,
    type TEXT NOT NULL,
    subject TEXT NOT NULL,
    category TEXT NOT NULL,
    extension TEXT NOT NULL,
    segments TEXT[],
    tags TEXT[] NOT NULL,
    summary TEXT,
    trailer TEXT,
    file_created TIMESTAMP NOT NULL,
    file_edited TIMESTAMP NOT NULL,
    added TIMESTAMP DEFAULT NOW() NOT NULL,
    updated TIMESTAMP DEFAULT NOW() NOT NULL,
    duplicate BOOLEAN DEFAULT FALSE NOT NULL,
    meta JSONB NOT NULL,
    md5 TEXT NOT NULL
);

CREATE INDEX idx_media_md5 ON media(md5);
CREATE INDEX idx_media_duplicate ON media(duplicate);
