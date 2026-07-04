-- agent_os schema — MASTER_PLAN Phase 1
CREATE DATABASE IF NOT EXISTS agent_os;
USE agent_os;

CREATE TABLE IF NOT EXISTS artifact (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  kind VARCHAR(50) NOT NULL,          -- code, note, config, schema
  language VARCHAR(20),               -- python, c, swift, markdown, sql
  name VARCHAR(255),
  content LONGTEXT,
  checksum VARCHAR(64),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_kind (kind),
  INDEX idx_language (language),
  INDEX idx_name (name)
);

CREATE TABLE IF NOT EXISTS event_log (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  event_type VARCHAR(100) NOT NULL,
  payload JSON,
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_event_type (event_type),
  INDEX idx_timestamp (timestamp)
);

CREATE TABLE IF NOT EXISTS agent_state (
  agent_id VARCHAR(100) PRIMARY KEY,
  state_json JSON,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS gui_config (
  widget_id VARCHAR(100) PRIMARY KEY,
  config_json JSON,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_registry (
  agent_id VARCHAR(100) PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  capabilities JSON,
  registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
