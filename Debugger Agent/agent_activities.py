import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import requests
from temporalio import activity


def _safe_heartbeat(msg: Any) -> None:
    try:
        _safe_heartbeat(msg)
    except RuntimeError:
        pass


BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "Tracing MCP"))
sys.path.insert(0, str(BASE_DIR / "Query Normalized Output MCP"))

import query_server
import tracing_server

from common.config import LLM_API_KEY, OLLAMA_BASE_URL, OLLAMA_MODEL
from common.telemetry import init_tracer, record_explicit_trace

AVAILABLE_TOOLS_SPEC = [
    {
        "name": "get_recent_traces",
        "description": "Get latest execution spans from Generated Traces/traces.json",
        "parameters": {"limit": "int"},
    },
    {
        "name": "find_failed_spans",
        "description": "Find spans that recorded errors or failures during pipeline execution",
        "parameters": {},
    },
    {
        "name": "get_pipeline_latency_summary",
        "description": "Get execution latency averages and min/max for each pipeline activity",
        "parameters": {},
    },
    {
        "name": "run_duckdb_sql",
        "description": "Execute a read-only SQL SELECT query on the de-identified DuckDB database",
        "parameters": {"query": "string"},
    },
    {
        "name": "get_table_schemas",
        "description": "Get DuckDB table schemas and column datatypes",
        "parameters": {},
    },
    {
        "name": "verify_deidentification_compliance",
        "description": "Run HIPAA Safe Harbor audit on DuckDB tables to verify no PII leaked",
        "parameters": {},
    },
    {
        "name": "get_clinical_summary_stats",
        "description": "Get high-level summary of patients, encounters, and costs",
        "parameters": {},
    },
]


def _call_ollama_or_llm(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """Attempts to call Ollama (OpenAI-compatible endpoint). Falls back to deterministic rule engine if unreachable."""
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if LLM_API_KEY and LLM_API_KEY != "ollama":
        headers["Authorization"] = f"Bearer {LLM_API_KEY}"

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "temperature": 0.1,
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return {"content": content, "source": "ollama"}
    except Exception:
        pass

    # Deterministic fallback reasoning for CI, tests, and offline development
    user_query = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            user_query = m.get("content", "").lower()
            break

    if "audit" in user_query or "compliance" in user_query or "hipaa" in user_query or "safe harbor" in user_query:
        return {
            "thought": "The user wants to verify HIPAA Safe Harbor de-identification compliance. I will use verify_deidentification_compliance.",
            "tool_call": {"name": "verify_deidentification_compliance", "arguments": {}},
            "source": "fallback_reasoner",
        }
    elif "fail" in user_query or "error" in user_query or "crash" in user_query:
        return {
            "thought": "The user wants to identify errors in the pipeline. I will inspect failed spans using find_failed_spans.",
            "tool_call": {"name": "find_failed_spans", "arguments": {}},
            "source": "fallback_reasoner",
        }
    elif "trace" in user_query or "span" in user_query:
        return {
            "thought": "The user is asking about execution traces. I will retrieve the recent traces using get_recent_traces.",
            "tool_call": {"name": "get_recent_traces", "arguments": {"limit": 5}},
            "source": "fallback_reasoner",
        }
    elif "latency" in user_query or "performance" in user_query or "speed" in user_query or "benchmark" in user_query:
        return {
            "thought": "The user is asking about latency benchmarks. I will retrieve latency metrics using get_pipeline_latency_summary.",
            "tool_call": {"name": "get_pipeline_latency_summary", "arguments": {}},
            "source": "fallback_reasoner",
        }
    elif "schema" in user_query or "tables" in user_query:
        return {
            "thought": "The user wants to see the database schema. I will run get_table_schemas.",
            "tool_call": {"name": "get_table_schemas", "arguments": {}},
            "source": "fallback_reasoner",
        }
    elif "select" in user_query or "sql" in user_query or "cost" in user_query or "patient" in user_query:
        return {
            "thought": "The user is asking for clinical data summary. I will query clinical summary stats.",
            "tool_call": {"name": "get_clinical_summary_stats", "arguments": {}},
            "source": "fallback_reasoner",
        }
    else:
        return {
            "thought": "I will inspect recent traces and database summary to answer the question.",
            "tool_call": {"name": "get_recent_traces", "arguments": {"limit": 3}},
            "source": "fallback_reasoner",
        }


@activity.defn
async def llm_reasoning_activity(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Temporal activity executing one reasoning step of the Debugger Agent."""
    start_t = time.time()
    tracer = init_tracer("debugger-agent")
    messages = input_data.get("messages", [])

    with tracer.start_as_current_span("llm_reasoning_activity") as span:
        _safe_heartbeat("Prompting LLM / Reasoning engine")
        span.set_attribute("message_count", len(messages))

        result = _call_ollama_or_llm(messages)
        duration = round((time.time() - start_t) * 1000, 2)
        result["duration_ms"] = duration

        record_explicit_trace(
            "llm_reasoning_activity",
            {"duration_ms": duration, "source": result.get("source")},
            status="OK",
            duration_ms=duration,
        )
        return result


@activity.defn
async def execute_mcp_tool_activity(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    """Temporal activity durably executing an MCP tool call with OpenTelemetry tracing."""
    start_t = time.time()
    tool_name = tool_call.get("name")
    args = tool_call.get("arguments", {})
    tracer = init_tracer("mcp-tool-executor")

    with tracer.start_as_current_span(f"mcp_tool_{tool_name}") as span:
        _safe_heartbeat(f"Executing tool {tool_name}")
        span.set_attribute("tool.name", str(tool_name))
        span.set_attribute("tool.args", json.dumps(args))

        output_str = ""
        error_msg = None

        try:
            if tool_name == "get_recent_traces":
                output_str = tracing_server.get_recent_traces(limit=args.get("limit", 10))
            elif tool_name == "get_trace_details":
                output_str = tracing_server.get_trace_details(trace_id=args.get("trace_id", ""))
            elif tool_name == "find_failed_spans":
                output_str = tracing_server.find_failed_spans()
            elif tool_name == "get_pipeline_latency_summary":
                output_str = tracing_server.get_pipeline_latency_summary()
            elif tool_name == "run_duckdb_sql":
                output_str = query_server.run_duckdb_sql(query=args.get("query", ""))
            elif tool_name == "get_table_schemas":
                output_str = query_server.get_table_schemas()
            elif tool_name == "verify_deidentification_compliance":
                output_str = query_server.verify_deidentification_compliance()
            elif tool_name == "get_clinical_summary_stats":
                output_str = query_server.get_clinical_summary_stats()
            else:
                error_msg = f"Unknown tool: {tool_name}"
                output_str = json.dumps({"error": error_msg})

        except Exception as e:
            error_msg = str(e)
            output_str = json.dumps({"error": error_msg})

        duration = round((time.time() - start_t) * 1000, 2)
        status = "ERROR" if error_msg else "OK"

        record_explicit_trace(
            f"mcp_{tool_name}",
            {"duration_ms": duration, "tool": tool_name},
            status=status,
            error_message=error_msg,
            duration_ms=duration,
        )

        return {
            "tool_name": tool_name,
            "output": output_str,
            "duration_ms": duration,
            "status": status,
        }
