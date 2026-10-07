# Temporal Agentic Design: Clinical Data De-identification, Analytics & Developer Debugger

An end-to-end distributed system orchestrating clinical data de-identification (HIPAA Safe Harbor) using **Temporal**, persisting queryable analytics into **DuckDB** and **Parquet**, emitting real-time **OpenTelemetry** traces, exposing services via **Model Context Protocol (MCP)**, and diagnosed by an **Ollama-first Developer Agent** with a **Streamlit** dashboard.

---

## 🌟 Highlights

- **Temporal Durable Orchestration**: Fault-tolerant pipeline workflows with custom exponential retry policies, activity heartbeats, dynamic progress queries, and mid-flight signals.
- **HIPAA Safe Harbor Compliance**: Salted SHA-256 pseudonymization, deterministic patient-consistent date shifting (-180 to +180 days), 90+ age bucketization, 3-digit ZIP coarsening, and clinical note regex redaction.
- **High-Performance Analytics**: Embedded DuckDB database and partitioned Parquet tables in `Output Aligned Queryable Data/`.
- **Continuous & Mid-Run Failure Telemetry**: Real-time OpenTelemetry span flushing to `Generated Traces/traces.json`. Catches activity failures, retries, and errors even on sudden pipeline terminations.
- **Model Context Protocol (MCP)**:
  - `Tracing MCP`: Trace lookup, failed span identification, latency percentiles.
  - `Query Normalized Output MCP`: Read-only SQL queries, table schemas, and automated compliance verification.
- **Developer Debugger Agent & UI**: ReAct agent (Ollama local default with offline fallback) and interactive Streamlit UI for instant root-cause analysis.
- **Production Scalability**: Docker Compose local development stack and Kubernetes manifests with Horizontal Pod Autoscaler (HPA).
- **CI / CD**: Automated GitHub Actions workflow (`.github/workflows/ci.yml`) running `ruff`, `mypy`, and `pytest`.

---

## 🚀 Quickstart

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/vigneshSrinivasan2005/Temporal-Agentic-Design.git
cd Temporal-Agentic-Design

# Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Download Kaggle Clinical Data

Ensure your `~/.kaggle/kaggle.json` credentials exist, then run:
```bash
python scripts/download_kaggle_data.py
```
*(See `Input Data Format 1/README.md` and `Input Data Format 2/README.md` for manual download commands and schema definitions).*

### 3. Run with Temporal

```bash
# Terminal 1: Start Temporal Development Server
temporal server start-dev

# Terminal 2: Start Pipeline Worker
python Mock-Data-Pipeline/worker.py

# Terminal 3: Trigger the Pipeline
python Mock-Data-Pipeline/run_pipeline.py
```

### 4. Launch Debugger Agent UI

```bash
streamlit run "Debugger Agent/app.py"
```
Navigate to `http://localhost:8501` to chat with the agent, audit HIPAA compliance, inspect traces, or run DuckDB SQL queries.

---

## 🛠️ Tracing & Diagnostics via MCP

You can directly run or connect standard MCP clients to either MCP server:

```bash
# Tracing MCP
python "Tracing MCP/server.py"

# Query Normalized Output MCP
python "Query Normalized Output MCP/server.py"
```

---

## 🐳 Docker & Kubernetes Scaling

### Docker Compose
```bash
# Launch Temporal, Worker, Jaeger, and Streamlit
docker compose up -d

# Scale pipeline workers horizontally
docker compose up -d --scale pipeline-worker=3
```

### Kubernetes (K8s) Deployment
```bash
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/storage-pvc.yaml
kubectl apply -f k8s/worker-deployment.yaml
kubectl apply -f k8s/worker-hpa.yaml
```

---

## 🧪 Testing & CI

```bash
# Linting & Formatting
ruff check .
ruff format --check .

# Type Checking
mypy common/ "Mock-Data-Pipeline/" "Output Aligned Queryable Data/" "Tracing MCP/" "Query Normalized Output MCP/" "Debugger Agent/"

# Automated Tests
pytest -v tests/
```
