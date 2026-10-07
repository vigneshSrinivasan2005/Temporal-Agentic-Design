import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
from temporalio import activity


def _safe_heartbeat(msg: Any) -> None:
    try:
        _safe_heartbeat(msg)
    except RuntimeError:
        pass


# Add parent and local directories to path for flexible imports
CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))
storage_dir = PARENT_DIR / "Output Aligned Queryable Data"
if str(storage_dir) not in sys.path:
    sys.path.insert(0, str(storage_dir))

import db as storage_db
from deidentifier import ClinicalDeidentifier

from common.config import (
    DEID_SALT,
    INPUT_ENCOUNTERS_CSV,
    INPUT_PATIENTS_CSV,
    OUTPUT_DIR,
    OUTPUT_DUCKDB_PATH,
)
from common.telemetry import init_tracer, record_explicit_trace

_SHARED_PATIENT_MAPPING: Dict[str, str] = {}
_PROCESSED_PATIENTS_DF: Optional[pd.DataFrame] = None
_PROCESSED_ENCOUNTERS_DF: Optional[pd.DataFrame] = None


@activity.defn
async def validate_inputs_activity(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validates existence and schema of input Kaggle CSV files."""
    start_t = time.time()
    tracer = init_tracer()

    patients_path = Path(config.get("patients_path") or INPUT_PATIENTS_CSV)
    encounters_path = Path(config.get("encounters_path") or INPUT_ENCOUNTERS_CSV)

    with tracer.start_as_current_span("validate_inputs_activity") as span:
        span.set_attribute("patients_path", str(patients_path))
        span.set_attribute("encounters_path", str(encounters_path))

        if not patients_path.exists():
            err_msg = f"Format 1 input file not found: {patients_path}. Please download Kaggle dataset or see Input Data Format 1/README.md"
            record_explicit_trace("validate_inputs_activity", {"error": err_msg}, status="ERROR", error_message=err_msg)
            raise FileNotFoundError(err_msg)

        if not encounters_path.exists():
            err_msg = f"Format 2 input file not found: {encounters_path}. Please download Kaggle dataset or see Input Data Format 2/README.md"
            record_explicit_trace("validate_inputs_activity", {"error": err_msg}, status="ERROR", error_message=err_msg)
            raise FileNotFoundError(err_msg)

        p_df = pd.read_csv(patients_path, nrows=5)
        e_df = pd.read_csv(encounters_path, nrows=5)

        duration = round((time.time() - start_t) * 1000, 2)
        res = {
            "status": "VALID",
            "patients_columns": list(p_df.columns),
            "encounters_columns": list(e_df.columns),
            "duration_ms": duration,
        }
        record_explicit_trace("validate_inputs_activity", res, status="OK", duration_ms=duration)
        return res


@activity.defn
async def deidentify_demographics_activity(config: Dict[str, Any]) -> Dict[str, Any]:
    """De-identifies Format 1 patient demographics using HIPAA Safe Harbor."""
    global _SHARED_PATIENT_MAPPING, _PROCESSED_PATIENTS_DF
    start_t = time.time()
    tracer = init_tracer()
    salt = config.get("salt") or DEID_SALT
    patients_path = Path(config.get("patients_path") or INPUT_PATIENTS_CSV)

    with tracer.start_as_current_span("deidentify_demographics_activity") as span:
        _safe_heartbeat("Reading patients file")
        df = pd.read_csv(patients_path)
        total_rows = len(df)
        span.set_attribute("raw_patients_count", total_rows)

        deid = ClinicalDeidentifier(salt=salt)
        _safe_heartbeat("Scrubbing PII and calculating age buckets")
        deid_df, mapping = deid.deidentify_demographics(df)

        _SHARED_PATIENT_MAPPING = mapping
        _PROCESSED_PATIENTS_DF = deid_df

        duration = round((time.time() - start_t) * 1000, 2)
        res = {
            "processed_patients": len(deid_df),
            "unique_pseudonyms": len(mapping),
            "age_buckets": deid_df["age_bucket"].value_counts().to_dict(),
            "duration_ms": duration,
        }
        record_explicit_trace("deidentify_demographics_activity", res, status="OK", duration_ms=duration)
        return res


@activity.defn
async def deidentify_encounters_activity(config: Dict[str, Any]) -> Dict[str, Any]:
    """De-identifies Format 2 clinical encounters and aligns with shifted dates."""
    global _SHARED_PATIENT_MAPPING, _PROCESSED_ENCOUNTERS_DF
    start_t = time.time()
    tracer = init_tracer()
    salt = config.get("salt") or DEID_SALT
    encounters_path = Path(config.get("encounters_path") or INPUT_ENCOUNTERS_CSV)

    with tracer.start_as_current_span("deidentify_encounters_activity") as span:
        _safe_heartbeat("Reading encounters file")
        df = pd.read_csv(encounters_path)
        span.set_attribute("raw_encounters_count", len(df))

        deid = ClinicalDeidentifier(salt=salt)
        _safe_heartbeat("Aligning patient date shifts and scrubbing notes")
        deid_encounters_df = deid.deidentify_encounters(df, patient_mapping=_SHARED_PATIENT_MAPPING)

        _PROCESSED_ENCOUNTERS_DF = deid_encounters_df
        duration = round((time.time() - start_t) * 1000, 2)
        res = {
            "processed_encounters": len(deid_encounters_df),
            "total_clinical_cost": float(deid_encounters_df["cost"].sum())
            if "cost" in deid_encounters_df.columns
            else 0.0,
            "duration_ms": duration,
        }
        record_explicit_trace("deidentify_encounters_activity", res, status="OK", duration_ms=duration)
        return res


@activity.defn
async def merge_and_normalize_activity(config: Dict[str, Any]) -> Dict[str, Any]:
    """Joins de-identified demographics with encounters to build summary statistics."""
    global _PROCESSED_PATIENTS_DF, _PROCESSED_ENCOUNTERS_DF
    start_t = time.time()
    tracer = init_tracer()

    with tracer.start_as_current_span("merge_and_normalize_activity") as span:
        _safe_heartbeat("Merging datasets on patient_deid_key")
        if _PROCESSED_PATIENTS_DF is None or _PROCESSED_ENCOUNTERS_DF is None:
            raise ValueError("Preceding deidentification steps did not populate dataframes.")

        merged = pd.merge(_PROCESSED_PATIENTS_DF, _PROCESSED_ENCOUNTERS_DF, on="patient_deid_key", how="left")

        duration = round((time.time() - start_t) * 1000, 2)
        res = {
            "total_merged_records": len(merged),
            "matched_patients_with_encounters": int(merged["encounter_id"].notna().sum())
            if "encounter_id" in merged.columns
            else 0,
            "duration_ms": duration,
        }
        record_explicit_trace("merge_and_normalize_activity", res, status="OK", duration_ms=duration)
        return res


@activity.defn
async def export_duckdb_parquet_activity(config: Dict[str, Any]) -> Dict[str, Any]:
    """Persists cleaned data into DuckDB database and partitioned Parquet files."""
    global _PROCESSED_PATIENTS_DF, _PROCESSED_ENCOUNTERS_DF
    start_t = time.time()
    tracer = init_tracer()

    db_path = Path(config.get("output_duckdb_path") or OUTPUT_DUCKDB_PATH)
    out_dir = Path(config.get("output_dir") or OUTPUT_DIR)

    with tracer.start_as_current_span("export_duckdb_parquet_activity") as span:
        _safe_heartbeat("Saving tables into DuckDB")
        storage_db.init_tables(_PROCESSED_PATIENTS_DF, _PROCESSED_ENCOUNTERS_DF, db_path=db_path)

        _safe_heartbeat("Writing Parquet files")
        parquet_files = storage_db.export_parquets(_PROCESSED_PATIENTS_DF, _PROCESSED_ENCOUNTERS_DF, output_dir=out_dir)

        duration = round((time.time() - start_t) * 1000, 2)
        res = {"duckdb_file": str(db_path), "parquet_files": parquet_files, "duration_ms": duration}
        record_explicit_trace("export_duckdb_parquet_activity", res, status="OK", duration_ms=duration)
        return res


@activity.defn
async def record_failure_telemetry_activity(failure_data: Dict[str, Any]) -> Dict[str, Any]:
    """Captures failure status, error message, and stack trace to traces.json."""
    error_msg = failure_data.get("error", "Unknown pipeline error")
    stage = failure_data.get("stage", "UNKNOWN")
    record_explicit_trace(
        name="pipeline_failure_telemetry",
        attributes={
            "failed_stage": stage,
            "error_type": failure_data.get("error_type", "PipelineException"),
            "workflow_id": failure_data.get("workflow_id", ""),
            "run_id": failure_data.get("run_id", ""),
        },
        status="ERROR",
        error_message=error_msg,
    )
    return {"status": "FAILURE_RECORDED", "logged_error": error_msg}
