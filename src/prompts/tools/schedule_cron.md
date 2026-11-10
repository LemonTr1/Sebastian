## Schedule Cron

> 此工具需要用户确认后方可执行。

Register a 5-field cron job (`minute hour day-of-month month day-of-week`). Requires user confirmation.

- `prompt` is injected to the agent when the job fires; write it as a complete, self-contained task.
- `recurring` defaults to true; false deletes the job after it fires once.
- `durable` defaults to true: persists to `~/.sebastian/.scheduled_tasks.json` and survives restarts.
- Expressions support `*`, `*/step`, ranges `a-b`, and lists `a,b,c`.
- Returns the generated job ID; keep it for later cancellation.
