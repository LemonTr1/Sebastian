## Grep

Search file contents with an extended regular expression (`grep -rHn -E -I`).

- `path` may be a file or a directory (absolute, `~` supported); binary files are skipped.
- Returns file path, line number, and matched text; overly long lines are truncated.
- At most 200 matching lines; refine `pattern` or `path` when the result is truncated.
- Prefer this over `bash grep`; use `Read` to inspect a match in context.
