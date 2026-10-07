from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PipelineConfig(BaseModel):
    patients_path: str = ""
    encounters_path: str = ""
    output_duckdb_path: str = ""
    salt: str = "temporal_agentic_safe_harbor_salt_2026"
    batch_size: int = 500
    export_parquet: bool = True


class PipelineProgress(BaseModel):
    workflow_id: str = ""
    run_id: str = ""
    stage: str = (
        "INITIALIZED"  # VALIDATING, DEIDENTIFYING_DEMO, DEIDENTIFYING_ENCOUNTERS, MERGING, EXPORTING, COMPLETED, FAILED
    )
    status: str = "RUNNING"  # RUNNING, PAUSED, COMPLETED, FAILED
    total_patients: int = 0
    deidentified_patients: int = 0
    total_encounters: int = 0
    deidentified_encounters: int = 0
    start_time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_update_time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error_message: Optional[str] = None
    stage_latencies_ms: Dict[str, float] = Field(default_factory=dict)


class PipelineResult(BaseModel):
    success: bool
    total_patients_processed: int
    total_encounters_processed: int
    duckdb_path: str
    parquet_files: List[str]
    duration_seconds: float
    error: Optional[str] = None


class TraceSpan(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    name: str
    start_time: str
    end_time: str
    duration_ms: float
    status: str  # OK, ERROR
    attributes: Dict[str, Any] = Field(default_factory=dict)
    events: List[Dict[str, Any]] = Field(default_factory=list)


class AgentMessage(BaseModel):
    role: str  # "user", "assistant", "system", "tool"
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
