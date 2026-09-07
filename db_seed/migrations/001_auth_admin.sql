-- Authentication/admin migration for existing POC databases.
-- Safe to run after the existing properties/city_centers tables exist.

CREATE TABLE IF NOT EXISTS users (
    id varchar(36) PRIMARY KEY,
    email varchar(320) NOT NULL UNIQUE,
    password_hash varchar(512) NOT NULL,
    role varchar(20) NOT NULL DEFAULT 'USER',
    is_active boolean NOT NULL DEFAULT true,
    email_verified boolean NOT NULL DEFAULT false,
    failed_login_count integer NOT NULL DEFAULT 0,
    locked_until timestamptz NULL,
    last_login_at timestamptz NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    profile jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);

CREATE TABLE IF NOT EXISTS auth_sessions (
    id varchar(36) PRIMARY KEY,
    user_id varchar(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash varchar(64) NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz NULL,
    user_agent text NULL
);
CREATE INDEX IF NOT EXISTS ix_auth_sessions_user_id ON auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS ix_auth_sessions_expires_at ON auth_sessions(expires_at);

CREATE TABLE IF NOT EXISTS email_verification_tokens (
    id varchar(36) PRIMARY KEY,
    user_id varchar(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash varchar(64) NOT NULL UNIQUE,
    expires_at timestamptz NOT NULL,
    used_at timestamptz NULL
);
CREATE INDEX IF NOT EXISTS ix_email_verification_tokens_user_id ON email_verification_tokens(user_id);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id varchar(36) PRIMARY KEY,
    user_id varchar(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash varchar(64) NOT NULL UNIQUE,
    expires_at timestamptz NOT NULL,
    used_at timestamptz NULL
);
CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_user_id ON password_reset_tokens(user_id);

CREATE TABLE IF NOT EXISTS user_favorites (
    user_id varchar(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    property_id integer NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, property_id)
);

CREATE TABLE IF NOT EXISTS saved_searches (
    id varchar(36) PRIMARY KEY,
    user_id varchar(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name varchar(200) NOT NULL,
    criteria jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_saved_searches_user_id ON saved_searches(user_id);

CREATE TABLE IF NOT EXISTS recently_viewed_properties (
    user_id varchar(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    property_id integer NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    viewed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, property_id)
);
CREATE INDEX IF NOT EXISTS ix_recently_viewed_user_time ON recently_viewed_properties(user_id, viewed_at);

CREATE TABLE IF NOT EXISTS property_ownership (
    property_id integer PRIMARY KEY REFERENCES properties(id) ON DELETE CASCADE,
    owner_type varchar(20) NOT NULL,
    owner_id varchar(36) NULL,
    owner_name varchar(255) NOT NULL,
    owner_email varchar(320) NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS property_flags (
    property_id integer PRIMARY KEY REFERENCES properties(id) ON DELETE CASCADE,
    is_published boolean NOT NULL DEFAULT true,
    is_featured boolean NOT NULL DEFAULT false,
    is_archived boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS admin_audit_logs (
    id varchar(36) PRIMARY KEY,
    admin_user_id varchar(36) NULL REFERENCES users(id) ON DELETE SET NULL,
    action varchar(100) NOT NULL,
    resource_type varchar(100) NOT NULL,
    resource_id varchar(100) NULL,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_admin_audit_logs_action ON admin_audit_logs(action);
CREATE INDEX IF NOT EXISTS ix_admin_audit_logs_created_at ON admin_audit_logs(created_at);

CREATE TABLE IF NOT EXISTS admin_settings (
    key varchar(100) PRIMARY KEY,
    value text NOT NULL,
    updated_by varchar(36) NULL REFERENCES users(id) ON DELETE SET NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
