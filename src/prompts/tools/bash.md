## Bash Tool

> 此工具需要用户确认后方可执行。

### When to use

**Use Bash only when no structured tool fits:**
- Delete / rename / move / copy files and directories (`rm`, `mv`, `cp`, `rsync`, `mkdir -p`)
- Compress / extract archives (`tar`, `zip`, `unzip`, `gzip`)
- Change permissions (`chmod`, `chown`)
- Install packages (`pip install`, `npm install`, `brew`, `apt`)
- Build / test / lint (`make`, `npm run build`, `pytest`, `cargo test`, `eslint`)
- Git operations beyond status (`clone`, `pull`, `push`, `merge`)
- Download files (`curl -O`, `wget`)

**Do NOT use Bash to:**
- Read files → `Read`
- Search file contents → `Grep`
- List files by pattern → `Glob`
- Replace text inside files → `Edit`
- Create files with content → `Write`

### Execution rules

- Commands start in `$HOME`; use absolute paths or `cd` for other directories.
- Prefer single-line commands (`&&` / `;` chaining). Use heredocs for multi-line content.
- A non-zero exit code means failure — read `stderr` and fix before continuing.

### Output

Returns `stdout`, `stderr`, and `returncode` (0 = success). On timeout the process is killed and partial output is returned.
