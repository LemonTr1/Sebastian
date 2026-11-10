## Question

Ask the user one blocking question and wait for the answer.

- Use only when a missing decision would significantly change the result (tech stack, naming, scope confirmation, ambiguous requirements, preferences).
- Enumerate 2-6 mutually exclusive short options when possible; users can always type free text, so do not add an "Other" option.
- Ask one question at a time, at most 2 per task. Do not use it for trivial choices you can reasonably assume.
- `timeout` defaults to 300 seconds (range 5-3600).
- If the status is timeout/cancelled/unavailable, do not retry: continue with a stated assumption, or ask in your reply and end the turn.
