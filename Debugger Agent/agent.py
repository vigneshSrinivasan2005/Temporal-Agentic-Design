import asyncio
import json
import logging
import sys
import uuid
from pathlib import Path
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "Debugger Agent"))

from agent_activities import execute_mcp_tool_activity, llm_reasoning_activity

from common.config import AGENT_TASK_QUEUE, TEMPORAL_HOST, TEMPORAL_NAMESPACE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def run_standalone_agent(prompt: str) -> Dict[str, Any]:
    """Runs the ReAct Debugger Agent directly without requiring an active Temporal Server."""
    messages = [
        {"role": "system", "content": "You are the Temporal Pipeline Debugger Agent."},
        {"role": "user", "content": prompt},
    ]

    reasoning = await llm_reasoning_activity({"messages": messages})
    tool_call = reasoning.get("tool_call")
    thought = reasoning.get("thought", "")

    tool_result = None
    if tool_call:
        tool_result = await execute_mcp_tool_activity(tool_call)

    return {
        "prompt": prompt,
        "thought": thought,
        "tool_call": tool_call,
        "tool_result": tool_result,
        "content": reasoning.get("content"),
    }


async def run_temporal_agent(prompt: str) -> Dict[str, Any]:
    """Runs the Debugger Agent inside Temporal via DebuggerAgentWorkflow."""
    from temporalio.client import Client

    client = await Client.connect(TEMPORAL_HOST, namespace=TEMPORAL_NAMESPACE)
    wf_id = f"debugger-agent-{uuid.uuid4().hex[:8]}"

    handle = await client.start_workflow(
        "DebuggerAgentWorkflow",
        prompt,
        id=wf_id,
        task_queue=AGENT_TASK_QUEUE,
    )
    res = await handle.result()
    return res


async def main():
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Audit HIPAA Safe Harbor compliance of the output DuckDB tables"
    print(f"\n[*] Querying Debugger Agent: '{prompt}'...")
    try:
        res = await run_temporal_agent(prompt)
        print("[+] Executed via Temporal Workflow:")
    except Exception as e:
        print(f"[!] Temporal server unreachable ({e}). Running via Standalone ReAct Agent:")
        res = await run_standalone_agent(prompt)

    print(json.dumps(res, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
