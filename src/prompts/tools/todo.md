## Todo

Rewrite the current task plan for multi-step work (maximum 10 items).

- Each item has `content` and `status` (`pending` / `in_progress` / `completed`).
- Exactly one item may be `in_progress` at a time.
- Always send the full list; it replaces the previous plan.
- Update immediately after finishing each item. The plan is shown to the user and re-injected as a reminder.
- Skip `todo` for single-step tasks.
