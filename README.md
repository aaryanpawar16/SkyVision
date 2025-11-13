# ✈️ SkyVision — Multimodal Travel Media Search

> **AI-powered airport and airline logo search using MariaDB Vector, CLIP embeddings, and Streamlit**

SkyVision lets you search **visually similar airports and airline logos** using **natural language, images, or both**.  
Type “beautiful Asian airports with glass facades” — and get airports that *look* like what you imagined.  
Or upload a logo to find visually related airlines.

<img width="3840" height="2642" alt="Skyvision Architecture" src="https://github.com/user-attachments/assets/5b7b7eb9-393d-4d20-a084-4e56a561b930" />

---

## 🚀 Key Features

| Capability | Description |
|-------------|--------------|
| 🧠 **Text → Image Search** | Find airports visually matching your description (“airports with indoor gardens and bamboo ceilings”) |
| 🖼️ **Image → Image Search** | Upload an airline logo to find similar logos across carriers |
| 🔀 **Hybrid Multimodal Search** | Combine text + image embeddings with tunable weights |
| 🌍 **Filters & Metadata** | Filter results by country, style, or image availability |
| ⚡ **MariaDB Vector Search** | Vector indexing + semantic similarity via `VECTOR_COSINE_DISTANCE` |
| 🔧 **Robust ETL Pipeline** | Scripts for image localization, embedding generation, and data ingestion |
| 🎨 **Modern Streamlit UI** | Clean card layout, auto image refresh, and live backend health checks |

---

## 🏗️ Architecture Overview

User ─▶ Streamlit Frontend
│
▼
FastAPI Backend
│
▼
CLIP Embedding Model
│
▼
MariaDB Vector DB
├─ airports (text/image vectors)
└─ airlines (logo vectors)

markdown
Copy code

**Data Flow:**
1. `auto_add_image_urls.py` — fetches airport & airline image/logo mappings  
2. `localize_images.py` — downloads and caches media locally  
3. `embed_images.py` /  `embed_logos.py` — generate `.npy` embedding arrays  
4. `pipeline/load_to_mariadb.py` — loads all metadata + vectors into MariaDB tables  
5. `/search/text`, `/search/image`, `/search/hybrid` APIs serve query results

---

## ⚙️ Tech Stack

| Layer | Technologies |
|-------|---------------|
| **Frontend** | Streamlit, HTML/CSS, responsive card layout |
| **Backend API** | FastAPI, Pydantic, Python 3.12 |
| **Vector DB** | MariaDB 11.4+ with Vector Columns |
| **Embeddings** | OpenAI CLIP (`ViT-B/32` model via `sentence-transformers`) |
| **ETL / Pipeline** | Pandas, NumPy, Pillow, Requests, tqdm |
| **Infra** | Live link streamlit; works locally or cloud-hosted MariaDB |

---

## 🧩 Setup Instructions

### 1️⃣ Clone the repository
```bash
git clone https://github.com/aaryanpawar16/SkyVision.git
cd SkyVision
2️⃣ Create a Python environment

python -m venv .venv
source .venv/bin/activate     # on macOS/Linux
.venv\Scripts\activate        # on Windows
3️⃣ Install dependencies
cd backend
pip install -r requirements.txt

cd frontend
pip install -r requirements.txt
4️⃣ Configure environment
Create a .env file in the project root:

env

# Database
DATABASE_HOST=localhost
DATABASE_PORT=3306
DATABASE_USER=sky
DATABASE_PASSWORD=vision
DATABASE_NAME=skyvision

# Embeddings
EMBEDDING_MODEL=clip-ViT-B-32
EMBEDDING_DIM=512

# API
CORS_ALLOW_ORIGINS=*
5️⃣ Prepare Data (From Project Folder Root)
Run the data pipeline:

python scripts/auto_add_image_urls.py
python scripts/localize_images.py --overwrite
python scripts/embed_images.py
python scripts/embed_logos.py
python -m pipeline.load_to_mariadb --processed_dir data/processed --prefer_image
6️⃣ Run Backend

cd backend
uvicorn app.main:app --reload --port 8000
7️⃣ Run Frontend

cd frontend
streamlit run app.py
Then open http://localhost:8501 🌐

💡 Example Queries
Type	Input	Output
Text → Image	“beautiful Asian airports with glass facades”	Changi, Incheon, Doha, Tokyo Haneda
Filtered Search	“modern airports with art installations” + Country: India	Delhi, Mumbai, Hyderabad
Image → Image	Upload: Air-India-Logo.jpg	Finds Air India, Emirates, Qatar Airways, Singapore Airlines
Hybrid	“airports with wooden ceilings” + reference image	Matches terminals with similar textures and design

🧠 Scoring Methodology (Hackathon)
Criteria	Weight
Impact & MariaDB Integration	30%
Technical Excellence	25%
Innovation & Creativity	20%
Execution & Completeness	15%
Learning & Community	10%
Total	1000 pts + 60 bonus possible

🏆 Highlights
Fully integrated with MariaDB Vector for real semantic + visual retrieval

Custom keyword boosting using SQL expressions

Hybrid embeddings (text + image weighted search)

Local image hosting with /media static path

Cache-busting to prevent stale results

Detailed metadata schema for style, tags, and attribution

📸 Demo Video (4 minutes)
🎬 Watch the Demo →
(Replace this with your final YouTube or Drive link)

⚖️ License
MIT License © 2025 — SkyVision Project
You’re free to use, modify, and build upon this work with attribution.

🌟 Acknowledgments
MariaDB Vector for powering semantic similarity search

OpenAI CLIP for multimodal embeddings

Streamlit for rapid, beautiful frontend UI

Sentence Transformers for Python embedding interface


SkyVision — “Search what you imagine, not just what you type.” ✈️












