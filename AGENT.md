# AGENT.md: Developer & Agent Guide for Temporal Agentic Design

Welcome, Developer / AI Agent! This guide outlines how to operate, maintain, and extend this repository.

---

## 1. System Architecture Overview

This repository implements a **durable, enterprise-grade healthcare data de-identification and normalization pipeline** orchestrated by Temporal, stored in DuckDB/Parquet, traced with OpenTelemetry, and diagnosed via Model Context Protocol (MCP) servers and an Ollama-first Debugger Agent.

### Key Components

```
Temporal-Agentic-Design/
├── Input Data Format 1/            # Demographics dataset (patients.csv)
├── Input Data Format 2/            # Clinical encounters dataset (encounters.csv)
├── Mock-Data-Pipeline/             # Core Temporal Workflow and Activities
│   ├── deidentifier.py             # HIPAA Safe Harbor de-identification engine
│   ├── activities.py               # Temporal Activities (validate, deid, merge, export, error telemetry)
│   ├── workflows.py                # ClinicalDataDeidPipelineWorkflow (try/except, signals, queries)
│   ├── worker.py                   # Temporal Worker with OpenTelemetry interceptor
│   └── run_pipeline.py             # CLI runner for the pipeline
├── Output Aligned Queryable Data/  # High-performance analytical storage
│   ├── clinical_analytics.duckdb   # DuckDB SQL database
│   ├── *.parquet                   # Cleaned partitioned Parquet files
│   └── db.py                       # DuckDB management, schema queries, compliance audits
├── Generated Traces/               # Distributed tracing repository
│   └── traces.json                 # Structured OpenTelemetry JSON traces emitted per-activity
├── Tracing MCP/                    # MCP server exposing trace diagnostics tools
├── Query Normalized Output MCP/   # MCP server exposing DuckDB SQL & HIPAA compliance audit tools
├── Debugger Agent/                 # Developer ReAct agent and UI
│   ├── activities.py               # Durable MCP tool call activity & LLM reasoning activity
│   ├── workflows.py                # DebuggerAgentWorkflow (Durable ReAct loop in Temporal)
│   ├── agent.py                    # Dual-mode agent runner (Temporal or Standalone)
│   └── app.py                      # Streamlit developer chat and analytics UI
├── skills/temporal-workflows/      # Antigravity skill for Temporal development best practices
├── k8s/                            # Production Kubernetes deployment and HPA autoscaling
└── tests/                          # Pytest suite with Temporal test environment
```

---

## 2. Ingesting Real Kaggle Datasets

Raw clinical files are placed into the respective format directories:
- **Format 1**: `Input Data Format 1/patients.csv` (Synthea Demographics)
- **Format 2**: `Input Data Format 2/encounters.csv` (Synthea Encounters)

### Kaggle CLI Automated Download
```bash
# Ensure ~/.kaggle/kaggle.json exists
python scripts/download_kaggle_data.py --dataset cpluzsh/synthea-synthetic-health-data
```

---

## 3. Operating the Temporal Data Pipeline

### Step 1: Start Temporal Development Server
```bash
temporal server start-dev
```
*(Temporal UI will be available at `http://localhost:8233`)*

### Step 2: Start the Pipeline Worker
```bash
python Mock-Data-Pipeline/worker.py
```

### Step 3: Trigger the Pipeline Workflow
```bash
python Mock-Data-Pipeline/run_pipeline.py
```

---

## 4. Model Context Protocol (MCP) Tools

The repository contains two standard FastMCP servers that can be consumed by the Debugger Agent or IDEs (Cursor/Antigravity):

### Tracing MCP (`Tracing MCP/server.py`)
- `get_recent_traces(limit: int)`: Inspect recent execution spans.
- `get_trace_details(trace_id: str)`: Drill down into individual activity spans.
- `find_failed_spans()`: Instantly isolate errors, exceptions, and failed activity retries.
- `get_pipeline_latency_summary()`: Execution duration percentiles and averages.

### Query Normalized Output MCP (`Query Normalized Output MCP/server.py`)
- `run_duckdb_sql(query: str)`: Run safe read-only analytical SQL queries on DuckDB.
- `get_table_schemas()`: View tables, column names, and types.
- `verify_deidentification_compliance()`: Automated HIPAA Safe Harbor audit scanner.
- `get_clinical_summary_stats()`: Patient counts, visit frequency, and cost summaries.

---

## 5. Developer Debugger Agent & UI

The agent uses local **Ollama** by default (`http://localhost:11434/v1`, model `llama3.2`). If Ollama is offline or unconfigured, it seamlessly falls back to a deterministic rule reasoner for tests and CI.

### Run Agent in Terminal
```bash
python "Debugger Agent/agent.py" "Audit the output tables for HIPAA compliance"
python "Debugger Agent/agent.py" "Find any failed spans in recent traces"
```

### Launch Streamlit Developer Dashboard
```bash
streamlit run "Debugger Agent/app.py"
```

---

## 6. Real-Time & Failure Telemetry Design

Telemetry spans are flushed immediately as each activity executes. Furthermore:
- `ClinicalDataDeidPipelineWorkflow` wraps every stage in a `try ... except ... finally` block.
- On any failure or retry exhaustion, `record_failure_telemetry_activity` executes immediately and logs the failure status, error message, and stack trace to `Generated Traces/traces.json`.
- Activities that completed prior to the failure remain preserved in `Generated Traces/traces.json`.

---

## 7. Scaling with Docker & Kubernetes

- **Local Multi-Service Stack**:
  ```bash
  docker compose up -d
  # Scale worker to 3 replicas
  docker compose up -d --scale pipeline-worker=3
  ```
- **Kubernetes**:
  ```bash
  kubectl apply -f k8s/configmap.yaml
  kubectl apply -f k8s/storage-pvc.yaml
  kubectl apply -f k8s/worker-deployment.yaml
  kubectl apply -f k8s/worker-hpa.yaml
  ```
