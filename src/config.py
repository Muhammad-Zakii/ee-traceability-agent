import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = DATA_DIR / "output"
CHROMA_DB_DIR = DATA_DIR / "chromadb"

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 100% Free & Local AI Configuration
# Ensure Ollama is installed and running on your machine (run: ollama pull llama3)
LLM_MODEL = "llama3" 
EMBEDDING_MODEL = "all-MiniLM-L6-v2" # Lightweight HuggingFace embedding model