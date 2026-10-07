import asyncio
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "Debugger Agent"))
sys.path.insert(0, str(BASE_DIR / "Output Aligned Queryable Data"))

import db as storage_db
from agent import run_standalone_agent

from common.config import OLLAMA_BASE_URL, OLLAMA_MODEL, OUTPUT_DUCKDB_PATH, TEMPORAL_HOST
from common.telemetry import read_all_traces

st.set_page_config(page_title="Temporal Developer Debugger", page_icon="🩺", layout="wide")

st.title("🩺 Temporal Pipeline Developer Debugger Agent")
st.caption("Agent-driven distributed pipeline diagnostics, HIPAA audit, and OpenTelemetry trace analysis")

# Sidebar Status
with st.sidebar:
    st.header("⚙️ System Status")
    st.write(f"**Temporal Host:** `{TEMPORAL_HOST}`")
    st.write(f"**Ollama Endpoint:** `{OLLAMA_BASE_URL}`")
    st.write(f"**Model:** `{OLLAMA_MODEL}`")
    st.markdown("---")

    db_exists = OUTPUT_DUCKDB_PATH.exists()
    st.metric("DuckDB Output Store", "Available" if db_exists else "Not Found")

    traces = read_all_traces()
    st.metric("Recorded OTel Spans", len(traces))

    st.markdown("---")
    st.markdown("### ⚡ Quick Diagnostics")
    audit_btn = st.button("🔍 Verify HIPAA Safe Harbor")
    errors_btn = st.button("⚠️ Inspect Failed Spans")
    perf_btn = st.button("⏱️ Pipeline Latency Summary")
    stats_btn = st.button("📊 Clinical Summary Stats")

# Session state initialization
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hello! I am your Developer Debugger Agent. I can audit the de-identified DuckDB dataset, trace failed Temporal activities, and inspect OpenTelemetry spans.",
        }
    ]

# Handle Quick Action Buttons
triggered_prompt = None
if audit_btn:
    triggered_prompt = (
        "Audit HIPAA Safe Harbor compliance of the output tables and verify that all direct PII is removed."
    )
elif errors_btn:
    triggered_prompt = "Find any failed spans or errors in the pipeline traces and explain the root cause."
elif perf_btn:
    triggered_prompt = "Give me the pipeline latency summary and activity execution speed benchmarks."
elif stats_btn:
    triggered_prompt = "Show the aggregated clinical summary statistics and cost analysis."

tab_chat, tab_traces, tab_db = st.tabs(["💬 Debugger Agent Chat", "📈 OpenTelemetry Spans", "🗄️ DuckDB Data Explorer"])

with tab_chat:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "tool_result" in msg and msg["tool_result"]:
                with st.expander("Tool Execution Details"):
                    st.json(msg["tool_result"])

    prompt = st.chat_input("Ask the debugger agent (e.g. 'Audit HIPAA compliance', 'Check failed spans', 'Run SQL')...")
    active_prompt = triggered_prompt or prompt

    if active_prompt:
        st.session_state.messages.append({"role": "user", "content": active_prompt})
        with st.chat_message("user"):
            st.markdown(active_prompt)

        with st.chat_message("assistant"):
            with st.spinner("Agent reasoning and executing MCP tools..."):
                res = asyncio.run(run_standalone_agent(active_prompt))

                thought = res.get("thought")
                tool_call = res.get("tool_call")
                tool_res = res.get("tool_result")
                content = res.get("content")

                if thought:
                    st.info(f"💡 **Agent Thought:** {thought}")

                if tool_call:
                    st.caption(f"🔧 Calling MCP Tool: `{tool_call.get('name')}`")

                output_text = ""
                if tool_res and "output" in tool_res:
                    output_text = (
                        f"**Tool Output (`{tool_res.get('tool_name')}`):**\n```json\n{tool_res.get('output')}\n```"
                    )
                elif content:
                    output_text = content
                else:
                    output_text = "Analysis completed."

                st.markdown(output_text)
                st.session_state.messages.append({"role": "assistant", "content": output_text, "tool_result": tool_res})

with tab_traces:
    st.subheader("Generated Traces & Telemetry")
    if traces:
        st.dataframe(
            pd.DataFrame(traces)[["name", "status", "duration_ms", "start_time", "end_time"]], use_container_width=True
        )
        st.write("Raw trace file: `Generated Traces/traces.json`")
    else:
        st.info("No traces generated yet. Run the pipeline to view real-time OpenTelemetry spans.")

with tab_db:
    st.subheader("DuckDB Normalized Clinical Data")
    if db_exists:
        query = st.text_area("SQL Query", value="SELECT * FROM clinical_summary LIMIT 10;", height=70)
        if st.button("Execute SQL"):
            try:
                rows = storage_db.run_query(query)
                if rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True)
                else:
                    st.warning("Query returned 0 rows.")
            except Exception as e:
                st.error(f"SQL Error: {e}")
    else:
        st.info("DuckDB database file not found. Run the pipeline to populate tables.")
