## Load Skill

Load the full content of a registered skill by its exact name.

- Available skills are listed in the system prompt; names are case-sensitive.
- The body is returned inside `<skill>` tags — follow its instructions for the current task.
- Load a skill only when its description matches the task; do not preload unrelated skills.
