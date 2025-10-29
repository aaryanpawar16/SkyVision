USE skyvision;

-- Build a 512-dim zero vector using CONCAT + REPEAT for brevity
-- (Matches VECTOR(512) defined in schema)
SET @z512 = CONCAT('[', REPEAT('0,', 511), '0]');

-- Minimal seed airports
INSERT INTO airports (id, name, city, country, iata, icao, latitude, longitude, image_url, metadata, embedding)
VALUES
  (1, 'Test Airport', 'Test City', 'Testland', 'TST', 'TST1', 10.0, 20.0,
   'https://example.com/test-airport.jpg',
   JSON_OBJECT('style','glass','tags', JSON_ARRAY('modern','green'), 'license','CC-BY'),
   VEC_FromText(@z512)
  ),
  (2, 'Demo Field', 'Demo City', 'Demostan', 'DMO', 'DMO1', 30.0, 40.0,
   NULL,
   JSON_OBJECT('style','steel','tags', JSON_ARRAY('industrial'), 'license','CC0'),
   VEC_FromText(@z512)
  )
ON DUPLICATE KEY UPDATE
  name=VALUES(name), city=VALUES(city), country=VALUES(country),
  iata=VALUES(iata), icao=VALUES(icao), latitude=VALUES(latitude), longitude=VALUES(longitude),
  image_url=VALUES(image_url), metadata=VALUES(metadata), embedding=VALUES(embedding);

-- Minimal seed airlines (logo similarity demo)
INSERT INTO airlines (id, name, alias, iata, icao, callsign, country, active, logo_url, metadata, embedding)
VALUES
  (100, 'SkyVision Airways', NULL, 'SV', 'SVN', 'SKYVISION', 'Testland', 'Y',
   'https://example.com/logo-sv.png',
   JSON_OBJECT('brand_colors', JSON_ARRAY('#0F62FE','#161616'), 'license','CC-BY'),
   VEC_FromText(@z512)
  ),
  (101, 'Demo Airlines', NULL, 'DM', 'DMO', 'DEMOAIR', 'Demostan', 'Y',
   NULL,
   JSON_OBJECT('brand_colors', JSON_ARRAY('#FF3B30','#1C1C1E'), 'license','CC0'),
   VEC_FromText(@z512)
  )
ON DUPLICATE KEY UPDATE
  name=VALUES(name), alias=VALUES(alias), iata=VALUES(iata), icao=VALUES(icao),
  callsign=VALUES(callsign), country=VALUES(country), active=VALUES(active),
  logo_url=VALUES(logo_url), metadata=VALUES(metadata), embedding=VALUES(embedding);
