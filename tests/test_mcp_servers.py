import json
import sys
from pathlib import Path

import pandas as pd
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "Tracing MCP"))
sys.path.insert(0, str(BASE_DIR / "Query Normalized Output MCP"))
sys.path.insert(0, str(BASE_DIR / "Output Aligned Queryable Data"))

import db as storage_db
import query_server
import tracing_server

from common.telemetry import record_explicit_trace


@pytest.fixture(autouse=True)
def setup_test_data(tmp_path):
    record_explicit_trace("test_activity_1", {"batch": 1}, status="OK", duration_ms=15.5)
    record_explicit_trace(
        "test_failing_activity",
        {"batch": 2},
        status="ERROR",
        error_message="Simulated activity timeout",
        duration_ms=50.0,
    )

    db_file = tmp_path / "test_clinical.duckdb"
    patients = pd.DataFrame(
        [
            {
                "patient_deid_key": "DEID-1111",
                "gender": "F",
                "race": "white",
                "ethnicity": "non-hispanic",
                "age_bucket": "30-39",
            },
            {
                "patient_deid_key": "DEID-2222",
                "gender": "M",
                "race": "asian",
                "ethnicity": "non-hispanic",
                "age_bucket": "90+",
            },
        ]
    )
    encounters = pd.DataFrame(
        [
            {
                "encounter_id": "ENC-001",
                "patient_deid_key": "DEID-1111",
                "start_time": "2026-01-01",
                "end_time": "2026-01-02",
                "cost": 150.0,
                "clinical_notes": "Followup visit",
            },
            {
                "encounter_id": "ENC-002",
                "patient_deid_key": "DEID-2222",
                "start_time": "2026-02-01",
                "end_time": "2026-02-01",
                "cost": 300.0,
                "clinical_notes": "Consultation",
            },
        ]
    )
    storage_db.init_tables(patients, encounters, db_path=db_file)

    orig_path = storage_db.OUTPUT_DUCKDB_PATH
    storage_db.OUTPUT_DUCKDB_PATH = db_file
    yield
    storage_db.OUTPUT_DUCKDB_PATH = orig_path


def test_tracing_mcp_recent_traces():
    res_str = tracing_server.get_recent_traces(limit=5)
    data = json.loads(res_str)
    assert isinstance(data, list)
    assert len(data) >= 2
    names = [t.get("name") for t in data]
    assert "test_activity_1" in names


def test_tracing_mcp_find_failed_spans():
    res_str = tracing_server.find_failed_spans()
    failed = json.loads(res_str)
    assert isinstance(failed, list)
    assert any(t.get("name") == "test_failing_activity" for t in failed)


def test_tracing_mcp_latency_summary():
    res_str = tracing_server.get_pipeline_latency_summary()
    metrics = json.loads(res_str)
    assert isinstance(metrics, dict)
    assert "test_activity_1" in metrics
    assert metrics["test_activity_1"]["avg_ms"] > 0


def test_query_mcp_schemas():
    res_str = query_server.get_table_schemas()
    schemas = json.loads(res_str)
    assert "deid_patients" in schemas
    assert "deid_encounters" in schemas


def test_query_mcp_run_sql():
    res_str = query_server.run_duckdb_sql("SELECT COUNT(*) AS cnt FROM deid_patients")
    data = json.loads(res_str)
    assert isinstance(data, list)
    assert data[0]["cnt"] == 2


def test_query_mcp_reject_destructive_sql():
    res_str = query_server.run_duckdb_sql("DROP TABLE deid_patients")
    data = json.loads(res_str)
    assert "error" in data
    assert "Disallowed destructive SQL operation" in data["error"]


def test_query_mcp_verify_compliance():
    res_str = query_server.verify_deidentification_compliance()
    audit = json.loads(res_str)
    assert audit.get("compliant") is True
    assert audit.get("total_patients") == 2
