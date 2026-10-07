import sys
from pathlib import Path

import pandas as pd
import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "Mock-Data-Pipeline"))
sys.path.insert(0, str(BASE_DIR / "Output Aligned Queryable Data"))

from pipeline_activities import (
    deidentify_demographics_activity,
    deidentify_encounters_activity,
    export_duckdb_parquet_activity,
    merge_and_normalize_activity,
    record_failure_telemetry_activity,
    validate_inputs_activity,
)
from pipeline_workflows import ClinicalDataDeidPipelineWorkflow


@pytest.fixture
def sample_data_paths(tmp_path):
    p_csv = tmp_path / "patients.csv"
    e_csv = tmp_path / "encounters.csv"
    duckdb_file = tmp_path / "out.duckdb"
    out_dir = tmp_path / "output_data"

    patients_df = pd.DataFrame(
        [
            {
                "Id": "P-101",
                "FIRST": "Jane",
                "LAST": "Doe",
                "SSN": "111-22-3333",
                "BIRTHDATE": "1980-04-12",
                "GENDER": "F",
                "RACE": "white",
                "ETHNICITY": "non-hispanic",
                "ZIP": "02138",
            },
            {
                "Id": "P-102",
                "FIRST": "John",
                "LAST": "Smith",
                "SSN": "444-55-6666",
                "BIRTHDATE": "1932-02-10",
                "GENDER": "M",
                "RACE": "asian",
                "ETHNICITY": "non-hispanic",
                "ZIP": "90210",
            },
        ]
    )
    encounters_df = pd.DataFrame(
        [
            {
                "Id": "E-201",
                "PATIENT": "P-101",
                "START": "2024-01-10T10:00:00Z",
                "STOP": "2024-01-10T12:00:00Z",
                "ENCOUNTERCLASS": "ambulatory",
                "CODE": "185345009",
                "DESCRIPTION": "Follow-up",
                "COST": 120.0,
                "NOTES": "Patient Jane Doe presented with normal vitals.",
            }
        ]
    )

    patients_df.to_csv(p_csv, index=False)
    encounters_df.to_csv(e_csv, index=False)

    return {
        "patients_path": str(p_csv),
        "encounters_path": str(e_csv),
        "output_duckdb_path": str(duckdb_file),
        "output_dir": str(out_dir),
    }


@pytest.mark.asyncio
async def test_clinical_pipeline_workflow_end_to_end(sample_data_paths):
    async with await WorkflowEnvironment.start_time_skipping() as env:
        task_queue = "test-clinical-queue"
        async with Worker(
            env.client,
            task_queue=task_queue,
            workflows=[ClinicalDataDeidPipelineWorkflow],
            activities=[
                validate_inputs_activity,
                deidentify_demographics_activity,
                deidentify_encounters_activity,
                merge_and_normalize_activity,
                export_duckdb_parquet_activity,
                record_failure_telemetry_activity,
            ],
        ):
            handle = await env.client.start_workflow(
                "ClinicalDataDeidPipelineWorkflow",
                sample_data_paths,
                id="test-pipeline-run-001",
                task_queue=task_queue,
            )

            # Query workflow status
            status = await handle.query("get_pipeline_status")
            assert status["status"] in ("RUNNING", "COMPLETED")

            result = await handle.result()
            assert result["success"] is True
            assert result["total_patients"] == 2
            assert result["total_encounters"] == 1
            assert Path(result["duckdb_file"]).exists()


@pytest.mark.asyncio
async def test_clinical_pipeline_workflow_failure_telemetry(tmp_path):
    # Pass missing files to trigger validation failure and record_failure_telemetry_activity
    invalid_config = {
        "patients_path": str(tmp_path / "non_existent_patients.csv"),
        "encounters_path": str(tmp_path / "non_existent_encounters.csv"),
    }
    async with await WorkflowEnvironment.start_time_skipping() as env:
        task_queue = "test-failure-queue"
        async with Worker(
            env.client,
            task_queue=task_queue,
            workflows=[ClinicalDataDeidPipelineWorkflow],
            activities=[
                validate_inputs_activity,
                deidentify_demographics_activity,
                deidentify_encounters_activity,
                merge_and_normalize_activity,
                export_duckdb_parquet_activity,
                record_failure_telemetry_activity,
            ],
        ):
            handle = await env.client.start_workflow(
                "ClinicalDataDeidPipelineWorkflow",
                invalid_config,
                id="test-failure-run-001",
                task_queue=task_queue,
            )

            with pytest.raises(Exception):
                await handle.result()

            # Query final status: should be marked FAILED with error message
            status = await handle.query("get_pipeline_status")
            assert status["status"] == "FAILED"
            assert (
                "Format 1 input file not found" in status["error_message"]
                or "Activity task failed" in status["error_message"]
            )
