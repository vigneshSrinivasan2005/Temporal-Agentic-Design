import argparse
import asyncio
import json
import logging
import sys
import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "Mock-Data-Pipeline"))

from temporalio.client import Client

from common.config import (
    DATA_PIPELINE_TASK_QUEUE,
    INPUT_ENCOUNTERS_CSV,
    INPUT_PATIENTS_CSV,
    OUTPUT_DUCKDB_PATH,
    TEMPORAL_HOST,
    TEMPORAL_NAMESPACE,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def main():
    parser = argparse.ArgumentParser(description="Run Temporal Clinical De-identification Pipeline")
    parser.add_argument("--patients", default=str(INPUT_PATIENTS_CSV), help="Path to patients.csv")
    parser.add_argument("--encounters", default=str(INPUT_ENCOUNTERS_CSV), help="Path to encounters.csv")
    parser.add_argument("--duckdb", default=str(OUTPUT_DUCKDB_PATH), help="Path to output DuckDB database")
    parser.add_argument("--workflow-id", default=None, help="Custom workflow ID")
    args = parser.parse_args()

    wf_id = args.workflow_id or f"clinical-deid-{uuid.uuid4().hex[:8]}"

    logging.info(f"Connecting to Temporal at {TEMPORAL_HOST}...")
    client = await Client.connect(TEMPORAL_HOST, namespace=TEMPORAL_NAMESPACE)

    config = {
        "patients_path": args.patients,
        "encounters_path": args.encounters,
        "output_duckdb_path": args.duckdb,
    }

    logging.info(f"Starting workflow '{wf_id}' on queue '{DATA_PIPELINE_TASK_QUEUE}'...")
    handle = await client.start_workflow(
        "ClinicalDataDeidPipelineWorkflow",
        config,
        id=wf_id,
        task_queue=DATA_PIPELINE_TASK_QUEUE,
    )

    logging.info(f"Workflow started! Run ID: {handle.result_run_id}")

    # Poll status query until completion
    while True:
        await asyncio.sleep(1.0)
        status = await handle.query("get_pipeline_status")
        stage = status.get("stage")
        state = status.get("status")
        logging.info(
            f"Workflow Status: {state} | Stage: {stage} | Patients: {status.get('total_patients')} | Encounters: {status.get('total_encounters')}"
        )

        if state in ("COMPLETED", "FAILED"):
            break

    result = await handle.result()
    print("\n--- Pipeline Completed Successfully ---")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
