from datetime import timedelta
from typing import Any, Dict, List

from temporalio import workflow
from temporalio.common import RetryPolicy


@workflow.defn
class DebuggerAgentWorkflow:
    """Temporal Agentic Workflow orchestrating durable ReAct loops with MCP tool activities."""

    def __init__(self):
        self._messages: List[Dict[str, Any]] = []
        self._status = "IDLE"
        self._pending_user_messages: List[str] = []

    @workflow.query
    def get_conversation(self) -> List[Dict[str, Any]]:
        """Queries full conversation history, agent thoughts, and tool execution outputs."""
        return self._messages

    @workflow.query
    def get_status(self) -> str:
        """Queries current status of the agent workflow."""
        return self._status

    @workflow.signal
    def submit_message(self, message: str) -> None:
        """Signal to send a developer question or command to the agent."""
        self._pending_user_messages.append(message)

    @workflow.run
    async def run(self, initial_prompt: str) -> Dict[str, Any]:
        self._status = "RUNNING"
        self._messages.append(
            {
                "role": "system",
                "content": (
                    "You are the Temporal Healthcare Pipeline Debugger Agent. "
                    "You inspect OpenTelemetry traces via Tracing MCP and audit normalized DuckDB data via Query Normalized Output MCP."
                ),
            }
        )
        self._messages.append({"role": "user", "content": initial_prompt})

        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_attempts=3,
        )

        max_iterations = 5
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Step 1: LLM Reasoning Activity
            reasoning_res = await workflow.execute_activity(
                "llm_reasoning_activity",
                {"messages": self._messages},
                start_to_close_timeout=timedelta(seconds=60),
                retry_policy=retry_policy,
            )

            thought = reasoning_res.get("thought", "")
            tool_call = reasoning_res.get("tool_call")
            content = reasoning_res.get("content")

            if thought:
                self._messages.append({"role": "assistant", "thought": thought, "content": f"[Thought]: {thought}"})

            # If tool call is requested, execute it durably
            if tool_call:
                self._messages.append(
                    {
                        "role": "assistant",
                        "tool_call": tool_call,
                        "content": f"Calling MCP tool: `{tool_call.get('name')}`",
                    }
                )

                # Step 2: Durable MCP Tool Activity Execution
                tool_res = await workflow.execute_activity(
                    "execute_mcp_tool_activity",
                    tool_call,
                    start_to_close_timeout=timedelta(minutes=2),
                    retry_policy=retry_policy,
                )

                tool_output = tool_res.get("output", "")
                self._messages.append({"role": "tool", "name": tool_res.get("tool_name"), "content": tool_output})

                # Produce final synthesizing response
                final_answer = (
                    f"Diagnostics Completed:\n"
                    f"- Action: Executed `{tool_res.get('tool_name')}`\n"
                    f"- Status: {tool_res.get('status')}\n"
                    f"- Result Preview:\n```json\n{tool_output[:500]}\n```"
                )
                self._messages.append({"role": "assistant", "content": final_answer})
                break

            elif content:
                self._messages.append({"role": "assistant", "content": content})
                break
            else:
                break

        self._status = "IDLE"
        return {"status": "COMPLETED", "messages": self._messages, "iterations": iteration}
