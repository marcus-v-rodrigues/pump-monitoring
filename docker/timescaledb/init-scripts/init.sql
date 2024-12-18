CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

CREATE TABLE IF NOT EXISTS pump_metrics (
    time TIMESTAMPTZ NOT NULL,
    pump_id TEXT,
    pressure FLOAT,
    flow_rate FLOAT,
    temperature FLOAT,
    vibration FLOAT,
    power_consumption FLOAT
);

SELECT create_hypertable('pump_metrics', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_pump_metrics_pump_id ON pump_metrics (pump_id, time DESC);