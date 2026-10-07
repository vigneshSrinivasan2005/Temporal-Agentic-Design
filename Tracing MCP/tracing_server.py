import json
import sys
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from common.config import TRACES_JSON_PATH
from common.telemetry import read_all_traces

mcp_app: Any = None
try:
    from fastmcp import FastMCP

    mcp_app = FastMCP("Tracing-MCP")
except ImportError:
    pass


def get_recent_traces(limit: int = 10) -> str:
    """Returns the most recent trace records logged to Generated Traces/traces.json."""
    traces = read_all_traces()
    if not traces:
        return json.dumps({"status": "NO_TRACES_FOUND", "message": f"No traces found in {TRACES_JSON_PATH}"})

    recent = traces[-limit:]
    summary = []
    for t in recent:
        summary.append(
            {
                "trace_id": t.get("trace_id"),
                "name": t.get("name"),
                "status": t.get("status"),
                "duration_ms": t.get("duration_ms"),
                "start_time": t.get("start_time"),
                "end_time": t.get("end_time"),
                "error": t.get("status_description") or t.get("attributes", {}).get("error"),
            }
        )
    return json.dumps(summary, indent=2)


def get_trace_details(trace_id: str) -> str:
    """Retrieves all spans and attributes belonging to a specific trace_id."""
    traces = read_all_traces()
    matching = [t for t in traces if t.get("trace_id") == trace_id]
    if not matching:
        return json.dumps({"status": "NOT_FOUND", "trace_id": trace_id})
    return json.dumps(matching, indent=2)


def find_failed_spans() -> str:
    """Finds all recorded spans that failed or logged errors, including error messages and stack traces."""
    traces = read_all_traces()
    failed = [
        t
        for t in traces
        if t.get("status") == "ERROR" or "error" in t.get("name", "").lower() or t.get("attributes", {}).get("error")
    ]
    if not failed:
        return json.dumps({"status": "ALL_HEALTHY", "message": "No failed spans found in traces.json."})
    return json.dumps(failed, indent=2)


def get_pipeline_latency_summary() -> str:
    """Computes execution time benchmarks across all completed activities."""
    traces = read_all_traces()
    latencies: Dict[str, List[float]] = {}
    for t in traces:
        name = t.get("name", "unknown")
        dur = t.get("duration_ms")
        if dur is not None and dur > 0:
            latencies.setdefault(name, []).append(dur)

    metrics = {}
    for name, durs in latencies.items():
        metrics[name] = {
            "invocations": len(durs),
            "avg_ms": round(sum(durs) / len(durs), 2),
            "min_ms": round(min(durs), 2),
            "max_ms": round(max(durs), 2),
        }
    return json.dumps(metrics, indent=2)


# If FastMCP is available, register tools
if mcp_app:
    mcp_app.tool()(get_recent_traces)
    mcp_app.tool()(get_trace_details)
    mcp_app.tool()(find_failed_spans)
    mcp_app.tool()(get_pipeline_latency_summary)


def run():
    if mcp_app:
        mcp_app.run()
    else:
        print(
            "Tracing MCP Direct CLI. Available tools: get_recent_traces, get_trace_details, find_failed_spans, get_pipeline_latency_summary"
        )
        print(get_recent_traces(5))


if __name__ == "__main__":
    run()
