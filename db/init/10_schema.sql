USE skyvision;

-- Airports table with VECTOR + JSON
DROP TABLE IF EXISTS airports;
CREATE TABLE airports (
  id           INT PRIMARY KEY,
  name         VARCHAR(255) NOT NULL,
  city         VARCHAR(255),
  country      VARCHAR(255),
  iata         VARCHAR(8),
  icao         VARCHAR(8),
  latitude     DOUBLE,
  longitude    DOUBLE,
  image_url    TEXT,
  metadata     JSON,                 -- e.g. {"style":"glass","tags":["modern","green"],"license":"CC-BY"}
  embedding    VECTOR(512) NOT NULL, -- must match backend EMBEDDING_DIM
  created_at   TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Airlines table with VECTOR + JSON
DROP TABLE IF EXISTS airlines;
CREATE TABLE airlines (
  id           INT PRIMARY KEY,
  name         VARCHAR(255) NOT NULL,
  alias        VARCHAR(255),
  iata         VARCHAR(8),
  icao         VARCHAR(8),
  callsign     VARCHAR(255),
  country      VARCHAR(255),
  active       CHAR(1),
  logo_url     TEXT,
  metadata     JSON,
  embedding    VECTOR(512) NOT NULL,
  created_at   TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Structured (BTREE) indexes for hybrid filters
CREATE INDEX idx_airports_country ON airports(country);
CREATE INDEX idx_airports_city    ON airports(city);
CREATE INDEX idx_airlines_country ON airlines(country);
CREATE INDEX idx_airlines_name    ON airlines(name);
