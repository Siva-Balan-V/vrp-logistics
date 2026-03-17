-- RouteForge VRP Optimizer – PostgreSQL Schema
-- Run with: psql -U postgres -d vrp -f schema.sql

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Optimization Jobs
CREATE TABLE IF NOT EXISTS optimization_jobs (
    job_id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status              VARCHAR(20) NOT NULL DEFAULT 'pending',
    n_locations         INT NOT NULL,
    n_vehicles          INT NOT NULL,
    routing_backend     VARCHAR(20) NOT NULL DEFAULT 'haversine',
    solver_time_s       FLOAT,
    total_distance_km   FLOAT,
    total_time_min      FLOAT,
    assigned_count      INT,
    unassigned_count    INT,
    request_json        JSONB,
    response_json       JSONB
);

CREATE INDEX idx_jobs_created ON optimization_jobs(created_at DESC);
CREATE INDEX idx_jobs_status  ON optimization_jobs(status);

-- Vehicle Routes
CREATE TABLE IF NOT EXISTS vehicle_routes (
    id              BIGSERIAL PRIMARY KEY,
    job_id          UUID NOT NULL REFERENCES optimization_jobs(job_id) ON DELETE CASCADE,
    vehicle_id      INT NOT NULL,
    route_json      JSONB NOT NULL,
    distance_km     FLOAT NOT NULL,
    time_minutes    FLOAT NOT NULL,
    packages        INT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_routes_job ON vehicle_routes(job_id);

-- Locations
CREATE TABLE IF NOT EXISTS locations (
    id              BIGSERIAL PRIMARY KEY,
    job_id          UUID NOT NULL REFERENCES optimization_jobs(job_id) ON DELETE CASCADE,
    location_id     INT NOT NULL,
    lat             DOUBLE PRECISION NOT NULL,
    lon             DOUBLE PRECISION NOT NULL,
    demand          INT NOT NULL DEFAULT 1,
    label           VARCHAR(200),
    is_depot        BOOLEAN NOT NULL DEFAULT FALSE,
    assigned        BOOLEAN NOT NULL DEFAULT FALSE,
    vehicle_id      INT
);

CREATE INDEX idx_locations_job      ON locations(job_id);
CREATE INDEX idx_locations_assigned ON locations(job_id, assigned);

-- Distance Matrix Cache
CREATE TABLE IF NOT EXISTS matrix_cache (
    cache_key       VARCHAR(64) PRIMARY KEY,
    backend         VARCHAR(20) NOT NULL,
    n_locations     INT NOT NULL,
    distance_km     BYTEA NOT NULL,
    duration_s      BYTEA NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours'
);

CREATE INDEX idx_matrix_expires ON matrix_cache(expires_at);

-- Cleanup expired matrices
CREATE OR REPLACE FUNCTION purge_expired_matrices()
RETURNS VOID LANGUAGE SQL AS $$
    DELETE FROM matrix_cache WHERE expires_at < NOW();
$$;
