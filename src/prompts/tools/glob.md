## Glob

Find paths under `scope` matching a glob pattern, returning results relative to `scope`.

- `scope` must be an existing directory; `pattern` supports `**`, e.g. `**/*.py` or `src/**/*.ts`.
- Recursive by default. At most 60 results are returned; narrow the pattern or scope when truncated.
- Use `Grep` to search file contents and `Read` to inspect a matched file.
