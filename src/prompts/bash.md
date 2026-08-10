## Bash Tool Specification
### When to use Bash vs. structured tools

**ALWAYS prefer structured tools over Bash when the operation has a dedicated tool:**

| Use structured tool | Instead of Bash |
|---------------------|---|
| `Read`              | `cat`, `head`, `tail`, `less`, `more` |
| `Write`             | `echo "..." > file`, `tee`, `>` redirection to create/overwrite files |
| `Edit`              | `sed -i`, `sed`, `awk` for in-place text replacement |
| `Glob`              | `ls`, `find` for listing files by pattern |
| `Grep`              | `grep`, `rg`, `ack`, `ag` for searching file contents |
| `Ls`                | `ls -la` for directory listing |

**Use Bash ONLY when:**
- Deleting files or directories (`rm`, `rmdir`)
- Renaming or moving files (`mv`)
- Copying files (`cp`, `rsync`)
- Creating directories (`mkdir -p`)
- Compressing or extracting archives (`tar`, `zip`, `unzip`, `gzip`)
- Changing file permissions (`chmod`, `chown`)
- Installing packages (`apt`, `yum`, `brew`, `pip install`, `npm install`)
- Running build commands (`make`, `cmake`, `npm run build`, `cargo build`)
- Running tests (`npm test`, `pytest`, `cargo test`)
- Running lint/formatters (`eslint`, `prettier`, `black`, `clang-format`)
- Git operations beyond basic status (`git clone`, `git pull`, `git push`, `git merge`)
- Downloading files (`curl -O`, `wget`)
- Any other ad-hoc system administration task

**CRITICAL:** Do NOT use Bash to read files, search for files, or perform string replacements inside files when the dedicated `Read`, `Grep`, `Glob`, or `Edit` tools are available. Structured tools provide better line-numbered output, safer editing semantics, and lower token consumption.

### Parameters

| Parameter           | Type    | Required | Description                                                                                                   |
|---------------------|---------|---|---------------------------------------------------------------------------------------------------------------|
| `command`           | string  | Yes | The shell command to execute. Use single-line commands when possible. For multi-line, use heredocs or `&&` / `||` chaining. |
| `run_in_background` | boolean | No | Execute commands or code asynchronously in the background without blocking the execution of subsequent tools when it is true. Default: false. |

### Input schema

```json
{
  "command": "string (required)",
  "run_in_background": "boolean (optional, default false)"
}
```

### Output

Returns an object with:
- `stdout`: Standard output text
- `stderr`: Standard error text
- `returncode`: Process exit code (0 = success, non-zero = failure)

### Working directory

The sandbox is anchored to the user's home directory (`/home/user`). All Bash commands execute with `/home/user` as the initial working directory, regardless of where the agent process was started. Use absolute paths or `cd` within the command if you need to operate in a subdirectory.

### Sandbox restrictions

The Bash tool runs inside a bubblewrap sandbox with the following rules:

**File system:**
- The entire host filesystem is visible in read-only mode.
- The home directory (`/home/user`) and configured work directories (e.g., `~/workspace`, `~/Downloads`, `~/.cache`) are writable.
- Sensitive directories are **completely hidden** (tmpfs overlay): `~/.ssh`, `~/.gnupg`, `~/.aws`, `~/.azure`, `~/.config/gcloud`, `~/.mozilla`, `~/.bitcoin`, `~/.password-store`, `~/.local/share/keyrings`, browser profiles, command histories, etc.
- Sensitive files are **read-only protected**: `~/.bashrc`, `~/.zshrc`, `~/.profile`, `~/.gitconfig`, `~/.inputrc`, `~/.vimrc`, shell/toolchain configs. Attempting to write these returns "Operation not permitted".

**Network:**
- Network access is **allowed** (not isolated). `curl`, `wget`, `npm install`, `pip install`, and API calls work normally.
- Outbound connections are subject to host-level firewall rules, not sandbox-level filtering.

**Process isolation:**
- Runs in a separate PID, IPC, UTS, and cgroup namespace.
- All Linux capabilities are dropped (`--cap-drop ALL`).
- The sandbox process dies automatically if the parent agent process exits (`--die-with-parent`).
- A new session is created (`--new-session`) to prevent terminal signal leakage.

### Best practices

1. **Prefer single-line commands.** Chain operations with `&&` for sequential success-dependent steps, or `;` for independent steps.
   ```
   mkdir -p ~/workspace/project && cd ~/workspace/project && git init
   ```

2. **Use heredocs for multi-line input** when you need to write complex scripts or multi-line strings to a file. This avoids shell escaping issues:
   ```bash
   cat > ~/workspace/config.json << 'EOF'
   {
     "name": "my-project",
     "version": "1.0.0"
   }
   EOF
   ```
   Note: Use `<< 'EOF'` (with quotes around the delimiter) to prevent variable expansion.

3. **Always check exit codes.** A non-zero exit code means the command failed. Do not assume success. If a build or test fails, read the stderr and fix the issue before proceeding.

4. **Use absolute paths** always. The sandbox chdir is fixed to `/home/user`, so relative paths are resolved from there.

5. **Do NOT use Bash for file reading or content search.** Use `Read` for reading files, `Grep` for searching contents, `Glob` for listing files. These tools provide structured, line-numbered output that is easier for the model to reason about.

6. **Do NOT use Bash for file editing.** Use `Edit` for precise string replacements. `sed -i` is error-prone with special characters, indentation, and cross-platform compatibility. `Edit` preserves formatting and provides clear before/after semantics.

7. **Do NOT use Bash for file creation unless necessary.** Use `Write` to create new files. Only use Bash redirection (`echo ... > file`) when the content is generated by a previous command (e.g., `curl -o file.zip`).

8. **Be careful with destructive commands.** `rm -rf`, `mv` overwriting existing files, and `chmod -R` can cause data loss. Confirm with the user before running broad destructive operations.

### Common patterns

**Create a directory tree:**
```json
{"command": "mkdir -p ~/workspace/project/src/components"}
```

**Delete a file:**
```json
{"command": "rm ~/workspace/project/old-file.txt"}
```

**Rename a file:**
```json
{"command": "mv ~/workspace/project/old-name.ts ~/workspace/project/new-name.ts"}
```

**Copy a file:**
```json
{"command": "cp ~/workspace/project/template.json ~/workspace/project/config.json"}
```

**Download a file:**
```json
{"command": "curl -L -o ~/workspace/data.zip https://example.com/data.zip"}
```

**Extract an archive:**
```json
{"command": "unzip ~/workspace/data.zip -d ~/workspace/data/"}
```

**Install packages:**
```json
{"command": "pip install requests beautifulsoup4", "run_in_background": true}
```

**Run tests:**
```json
{"command": "cd ~/workspace/project && npm test"}
```

**Run a build:**
```json
{"command": "cd ~/workspace/project && make -j$(nproc)", "run_in_background": true}
```

**Check disk usage:**
```json
{"command": "du -sh ~/workspace/project/* | sort -h"}
```

**List running processes:**
```json
{"command": "ps aux | grep node"}
```

### Error handling

- **Exit code 0**: Success. stdout contains the result.
- **Exit code non-zero**: Command failed. Check stderr for the error message.
- **Timeout**: Command exceeded the timeout limit. The process is killed. stdout/stderr contain partial output. Increase `timeout` and retry if appropriate.
- **Permission denied**: You attempted to write to a read-only or hidden path (e.g., `~/.ssh`, `~/.bashrc`). This is expected sandbox behavior. Do not attempt to bypass it.
- **Command not found**: The executable is not in the sandbox PATH. Use absolute paths (e.g., `/usr/local/bin/my-tool`) or check installation.

### Security notes

- The sandbox prevents writing to sensitive configuration files, but **does not prevent reading them** if they are not in the deny_read list. Do not read or exfiltrate user credentials, API keys, or private keys.
- Network access is unrestricted. Be cautious with `curl | bash` patterns or executing untrusted remote scripts.
- All subprocesses inherit the sandbox restrictions. A command that spawns additional processes (e.g., `make` spawning compilers) is still constrained.