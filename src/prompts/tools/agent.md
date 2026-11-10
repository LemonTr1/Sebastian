## Agent

> 此工具需要用户确认后方可执行。

Dispatch a specialized sub-agent with an isolated context. Requires user confirmation.

- Provide `agent_name` exactly as listed and a self-contained `task` (goal, constraints, expected output) — the sub-agent cannot see the conversation.
- The sub-agent returns only its final result; summarize it for the user.
- Approving this call authorizes the sub-agent's internal tools; they are not confirmed one by one.
- Use `run_in_background=true` for long tasks whose result is not needed immediately.
- Do not dispatch for work you can finish with a single direct tool call.
