import os
from pathlib import Path

# Root project directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Input data directories
INPUT_FORMAT_1_DIR = BASE_DIR / "Input Data Format 1"
INPUT_FORMAT_2_DIR = BASE_DIR / "Input Data Format 2"

INPUT_PATIENTS_CSV = INPUT_FORMAT_1_DIR / "patients.csv"
INPUT_ENCOUNTERS_CSV = INPUT_FORMAT_2_DIR / "encounters.csv"

# Output data directories
OUTPUT_DIR = BASE_DIR / "Output Aligned Queryable Data"
OUTPUT_DUCKDB_PATH = OUTPUT_DIR / "clinical_analytics.duckdb"
OUTPUT_PATIENTS_PARQUET = OUTPUT_DIR / "patients_deidentified.parquet"
OUTPUT_ENCOUNTERS_PARQUET = OUTPUT_DIR / "encounters_deidentified.parquet"
OUTPUT_SUMMARY_PARQUET = OUTPUT_DIR / "patient_encounters_summary.parquet"

# Traces directory
TRACES_DIR = BASE_DIR / "Generated Traces"
TRACES_JSON_PATH = TRACES_DIR / "traces.json"

# Temporal Configuration
TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
DATA_PIPELINE_TASK_QUEUE = "clinical-deid-pipeline-queue"
AGENT_TASK_QUEUE = "debugger-agent-queue"

# Ollama / LLM Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
LLM_API_KEY = os.getenv("LLM_API_KEY", "ollama")

# De-identification Salt
DEID_SALT = os.getenv("DEID_SALT", "temporal_agentic_safe_harbor_salt_2026")
