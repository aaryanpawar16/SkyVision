#!/usr/bin/env bash
set -euo pipefail

# End-to-end seed:
# 1) Pull OpenFlights CSVs
# 2) Ingest → Parquet
# 3) (Optional) prepare image URL template
# 4) Embed with CLIP
# 5) Load into MariaDB

PYTHON=${PYTHON:-python}
RAW_DIR=${RAW_DIR:-"data/raw/openflights"}
PROC_DIR=${PROC_DIR:-"data/processed"}
URLS_CSV=${URLS_CSV:-"data/external/image_urls.csv"}

DB_HOST=${DB_HOST:-"localhost"}
DB_PORT=${DB_PORT:-3306}
DB_USER=${DB_USER:-"sky"}
DB_PASSWORD=${DB_PASSWORD:-"vision"}
DB_NAME=${DB_NAME:-"skyvision"}

MODEL_NAME=${MODEL_NAME:-"clip-ViT-B-32"}
DIM=${DIM:-512}

mkdir -p "${RAW_DIR}" "data/external"

echo "→ Downloading OpenFlights CSVs into ${RAW_DIR}…"
# Official repo provides CSV with headers; adjust paths if needed.
curl -fsSL -o "${RAW_DIR}/airports.csv" https://raw.githubusercontent.com/MariaDB/openflights/refs/heads/master/airports.csv
curl -fsSL -o "${RAW_DIR}/airlines.csv" https://raw.githubusercontent.com/MariaDB/openflights/refs/heads/master/airlines.csv

echo "→ Ingesting CSVs → Parquet…"
${PYTHON} -m pipeline.ingest_openflights --csv_dir "${RAW_DIR}" --out_dir "${PROC_DIR}"

# Create a scaffold URLs CSV if not present (you can fill with real images later)
if [[ ! -f "${URLS_CSV}" ]]; then
  echo "entity_type,id,url,license,attribution,style,tags" > "${URLS_CSV}"
  # Add a couple placeholder rows (optional)
  echo "airport,1,https://upload.wikimedia.org/wikipedia/commons/7/78/Sample_Image.jpg,CC0,Wikimedia,glass,modern,green" >> "${URLS_CSV}" || true
fi

echo "→ Cleaning/validating image URLs list…"
${PYTHON} -m pipeline.fetch_images --input_csv "${URLS_CSV}"

echo "→ Generating embeddings with ${MODEL_NAME} (dim=${DIM})…"
${PYTHON} -m pipeline.embed_entities \
  --out_dir "${PROC_DIR}" \
  --urls_csv "${URLS_CSV}" \
  --model_name "${MODEL_NAME}" \
  --dim ${DIM} \
  --with_images

echo "→ Loading into MariaDB ${DB_HOST}:${DB_PORT}/${DB_NAME}…"
DB_HOST=${DB_HOST} DB_PORT=${DB_PORT} DB_USER=${DB_USER} DB_PASSWORD=${DB_PASSWORD} DB_NAME=${DB_NAME} \
${PYTHON} -m pipeline.load_to_mariadb --processed_dir "${PROC_DIR}" --prefer_image

echo "✔ Seed complete."
