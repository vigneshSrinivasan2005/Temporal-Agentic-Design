from datetime import timedelta
from typing import Any, Dict

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from common.models import PipelineProgress


@workflow.defn
class ClinicalDataDeidPipelineWorkflow:
    """Temporal workflow orchestrating the clinical data de-identification & normalization pipeline."""

    def __init__(self):
        self._progress = PipelineProgress()
        self._paused = False

    @workflow.query
    def get_pipeline_status(self) -> Dict[str, Any]:
        """Query method to inspect pipeline status and stage latencies in real-time."""
        return self._progress.model_dump()

    @workflow.signal
    def pause_pipeline(self) -> None:
        """Signal to pause workflow between stages."""
        self._paused = True
        self._progress.status = "PAUSED"

    @workflow.signal
    def resume_pipeline(self) -> None:
        """Signal to resume workflow execution."""
        self._paused = False
        self._progress.status = "RUNNING"

    @workflow.run
    async def run(self, config: Dict[str, Any]) -> Dict[str, Any]:
        self._progress.workflow_id = workflow.info().workflow_id
        self._progress.run_id = workflow.info().run_id
        self._progress.status = "RUNNING"

        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=3,
        )

        try:
            # Stage 1: Validation
            await self._wait_if_paused()
            self._progress.stage = "VALIDATING"
            val_res = await workflow.execute_activity(
                "validate_inputs_activity",
                config,
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=retry_policy,
            )
            self._progress.stage_latencies_ms["VALIDATING"] = val_res.get("duration_ms", 0.0)

            # Stage 2: Demographics De-identification
            await self._wait_if_paused()
            self._progress.stage = "DEIDENTIFYING_DEMO"
            demo_res = await workflow.execute_activity(
                "deidentify_demographics_activity",
                config,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=retry_policy,
            )
            self._progress.total_patients = demo_res.get("processed_patients", 0)
            self._progress.deidentified_patients = demo_res.get("unique_pseudonyms", 0)
            self._progress.stage_latencies_ms["DEIDENTIFYING_DEMO"] = demo_res.get("duration_ms", 0.0)

            # Stage 3: Encounters De-identification
            await self._wait_if_paused()
            self._progress.stage = "DEIDENTIFYING_ENCOUNTERS"
            enc_res = await workflow.execute_activity(
                "deidentify_encounters_activity",
                config,
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=retry_policy,
            )
            self._progress.total_encounters = enc_res.get("processed_encounters", 0)
            self._progress.deidentified_encounters = enc_res.get("processed_encounters", 0)
            self._progress.stage_latencies_ms["DEIDENTIFYING_ENCOUNTERS"] = enc_res.get("duration_ms", 0.0)

            # Stage 4: Merge & Normalization
            await self._wait_if_paused()
            self._progress.stage = "MERGING"
            merge_res = await workflow.execute_activity(
                "merge_and_normalize_activity",
                config,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=retry_policy,
            )
            self._progress.stage_latencies_ms["MERGING"] = merge_res.get("duration_ms", 0.0)

            # Stage 5: Export DuckDB & Parquet
            await self._wait_if_paused()
            self._progress.stage = "EXPORTING"
            export_res = await workflow.execute_activity(
                "export_duckdb_parquet_activity",
                config,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=retry_policy,
            )
            self._progress.stage_latencies_ms["EXPORTING"] = export_res.get("duration_ms", 0.0)

            self._progress.stage = "COMPLETED"
            self._progress.status = "COMPLETED"

            return {
                "success": True,
                "total_patients": self._progress.total_patients,
                "total_encounters": self._progress.total_encounters,
                "duckdb_file": export_res.get("duckdb_file"),
                "parquet_files": export_res.get("parquet_files", []),
                "stage_latencies_ms": self._progress.stage_latencies_ms,
            }

        except Exception as err:
            self._progress.status = "FAILED"
            root_cause = getattr(err, "cause", None)
            err_text = f"{err}: {root_cause}" if root_cause else str(err)
            self._progress.error_message = err_text

            # Immediately record failure telemetry
            try:
                await workflow.execute_activity(
                    "record_failure_telemetry_activity",
                    {
                        "error": err_text,
                        "error_type": type(err).__name__,
                        "stage": self._progress.stage,
                        "workflow_id": workflow.info().workflow_id,
                        "run_id": workflow.info().run_id,
                    },
                    start_to_close_timeout=timedelta(seconds=30),
                )
            except Exception:
                pass
            raise

    async def _wait_if_paused(self):
        while self._paused:
            await workflow.wait_condition(lambda: not self._paused)
