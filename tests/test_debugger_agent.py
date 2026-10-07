import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "Debugger Agent"))

from agent import run_standalone_agent
from agent_activities import execute_mcp_tool_activity, llm_reasoning_activity


@pytest.mark.asyncio
async def test_agent_reasoning_audit_intent():
    messages = [{"role": "user", "content": "Please verify HIPAA Safe Harbor compliance for the dataset."}]
    res = await llm_reasoning_activity({"messages": messages})
    assert "tool_call" in res
    assert res["tool_call"]["name"] == "verify_deidentification_compliance"


@pytest.mark.asyncio
async def test_agent_reasoning_failure_intent():
    messages = [{"role": "user", "content": "Why did the pipeline fail? Check for errors."}]
    res = await llm_reasoning_activity({"messages": messages})
    assert "tool_call" in res
    assert res["tool_call"]["name"] == "find_failed_spans"


@pytest.mark.asyncio
async def test_agent_mcp_tool_execution():
    tool_call = {"name": "get_recent_traces", "arguments": {"limit": 2}}
    tool_res = await execute_mcp_tool_activity(tool_call)
    assert tool_res["tool_name"] == "get_recent_traces"
    assert tool_res["status"] == "OK"
    assert "output" in tool_res


@pytest.mark.asyncio
async def test_standalone_agent_full_loop():
    prompt = "Inspect latency benchmarks and performance"
    res = await run_standalone_agent(prompt)
    assert res["prompt"] == prompt
    assert res["tool_call"] is not None
    assert res["tool_result"] is not None
    assert res["tool_result"]["status"] == "OK"
