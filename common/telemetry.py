import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace.status import StatusCode

from common.config import TRACES_JSON_PATH

_LOCK = threading.Lock()


class JsonFileSpanExporter(SpanExporter):
    """OpenTelemetry span exporter that writes structured JSON spans to file in real-time."""

    def __init__(self, file_path: Path = TRACES_JSON_PATH):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        with _LOCK:
            existing_records = []
            if self.file_path.exists() and self.file_path.stat().st_size > 0:
                try:
                    with open(self.file_path, "r", encoding="utf-8") as f:
                        existing_records = json.load(f)
                except Exception:
                    existing_records = []

            for span in spans:
                duration_ms = (
                    (span.end_time - span.start_time) / 1_000_000 if span.end_time and span.start_time else 0.0
                )
                record = {
                    "trace_id": format(span.context.trace_id, "032x"),
                    "span_id": format(span.context.span_id, "016x"),
                    "parent_span_id": format(span.parent.span_id, "016x") if span.parent else None,
                    "name": span.name,
                    "start_time": datetime.fromtimestamp(span.start_time / 1e9, timezone.utc).isoformat()
                    if span.start_time
                    else None,
                    "end_time": datetime.fromtimestamp(span.end_time / 1e9, timezone.utc).isoformat()
                    if span.end_time
                    else None,
                    "duration_ms": round(duration_ms, 2),
                    "status": "ERROR" if span.status.status_code == StatusCode.ERROR else "OK",
                    "status_description": span.status.description or "",
                    "attributes": dict(span.attributes or {}),
                    "events": [
                        {
                            "name": event.name,
                            "timestamp": datetime.fromtimestamp(event.timestamp / 1e9, timezone.utc).isoformat(),
                            "attributes": dict(event.attributes or {}),
                        }
                        for event in span.events
                    ],
                }
                existing_records.append(record)

            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(existing_records, f, indent=2)

        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass


_TRACER_INITIALIZED = False


def init_tracer(service_name: str = "temporal-clinical-pipeline") -> trace.Tracer:
    """Initializes OpenTelemetry tracer provider with JsonFileSpanExporter."""
    global _TRACER_INITIALIZED
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
        exporter = JsonFileSpanExporter()
        # Use SimpleSpanProcessor to ensure immediate synchronous write on span end
        processor = SimpleSpanProcessor(exporter)
        provider.add_span_processor(processor)
        _TRACER_INITIALIZED = True
    return trace.get_tracer(service_name)


def record_explicit_trace(
    name: str,
    attributes: Dict[str, Any],
    status: str = "OK",
    error_message: Optional[str] = None,
    duration_ms: float = 0.0,
) -> Dict[str, Any]:
    """Helper to record an explicit span directly to traces.json."""
    tracer = init_tracer()
    with tracer.start_as_current_span(name) as span:
        for k, v in attributes.items():
            span.set_attribute(k, v)
        if status == "ERROR":
            span.set_status(StatusCode.ERROR, description=error_message or "Activity failed")
            if error_message:
                span.set_attribute("error.message", error_message)
        else:
            span.set_status(StatusCode.OK)

    # Return formatted record
    return {
        "name": name,
        "status": status,
        "attributes": attributes,
        "error_message": error_message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def read_all_traces() -> List[Dict[str, Any]]:
    """Reads all recorded traces from traces.json."""
    if not TRACES_JSON_PATH.exists() or TRACES_JSON_PATH.stat().st_size == 0:
        return []
    with _LOCK:
        try:
            with open(TRACES_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
