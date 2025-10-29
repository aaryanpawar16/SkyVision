-- Create database, user, and grants (idempotent)
CREATE DATABASE IF NOT EXISTS skyvision
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

CREATE USER IF NOT EXISTS 'sky'@'%' IDENTIFIED BY 'vision';
GRANT ALL PRIVILEGES ON skyvision.* TO 'sky'@'%';
FLUSH PRIVILEGES;

-- Use the DB for subsequent scripts
USE skyvision;

-- Helpful modes (optional)
SET SESSION sql_mode = 'STRICT_ALL_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';
