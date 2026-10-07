import asyncio
import logging
import sys
from pathlib import Path

# Add directories to path
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
from temporalio.client import Client
from temporalio.contrib.opentelemetry import TracingInterceptor
from temporalio.worker import Worker

from common.config import DATA_PIPELINE_TASK_QUEUE, TEMPORAL_HOST, TEMPORAL_NAMESPACE
from common.telemetry import init_tracer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def run_worker():
    logging.info(f"Connecting to Temporal at {TEMPORAL_HOST} (namespace: {TEMPORAL_NAMESPACE})...")
    init_tracer("temporal-pipeline-worker")

    client = await Client.connect(
        TEMPORAL_HOST,
        namespace=TEMPORAL_NAMESPACE,
        interceptors=[TracingInterceptor()],
    )

    worker = Worker(
        client,
        task_queue=DATA_PIPELINE_TASK_QUEUE,
        workflows=[ClinicalDataDeidPipelineWorkflow],
        activities=[
            validate_inputs_activity,
            deidentify_demographics_activity,
            deidentify_encounters_activity,
            merge_and_normalize_activity,
            export_duckdb_parquet_activity,
            record_failure_telemetry_activity,
        ],
    )

    logging.info(f"Worker started listening on task queue: '{DATA_PIPELINE_TASK_QUEUE}'")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())
