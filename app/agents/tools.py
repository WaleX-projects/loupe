"""Tools that run through the agent's Strands DockerSandbox (tool_context.agent.sandbox).

No docker code lives here. The sandbox is created once in agents.py and passed to each Agent.
Full shell + file editing come from the sandbox's built-in tools (sandbox_shell, sandbox_file_editor);
agents.py decides which agents keep them. Everything below is extra, mostly read-only helpers.
"""
import hashlib
import posixpath
import shlex
import urllib.request

from strands import tool
from strands.sandbox.errors import SandboxTimeoutError
from strands.types.tools import ToolContext

MAX_OUTPUT = 20_000
SANDBOX_SHELL = "sandbox_shell"            # vended by DockerSandbox.get_tools()
SANDBOX_EDITOR = "sandbox_file_editor"     # vended by DockerSandbox.get_tools()


# ---------------------------------------------------------------- helpers
def _trunc(text: str, limit: int = MAX_OUTPUT) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + f"\n...[truncated {len(text) - limit} chars]...\n" + text[-half:]


def _wd(ctx: ToolContext) -> str:
    return getattr(ctx.agent.sandbox, "working_dir", None) or "/workspace"


async def _run(ctx: ToolContext, cmd: str, timeout: int = 120):
    """Run a shell command through the agent's sandbox. Returns (exit_code, output)."""
    try:
        r = await ctx.agent.sandbox.execute(cmd, timeout=timeout)
    except SandboxTimeoutError:
        return 124, f"[timed out after {timeout}s]"
    out = r.stdout or ""
    if r.stderr:
        out += ("\n" if out else "") + "[stderr]\n" + r.stderr
    return r.exit_code, _trunc(out)


async def _resolve(ctx: ToolContext, path: str):
    """Jail a path to the sandbox working dir (follows symlinks). Returns (path, error)."""
    wd = _wd(ctx)
    full = posixpath.normpath(posixpath.join(wd, path))
    code, out = await _run(ctx, f"realpath -m -- {shlex.quote(full)}", timeout=10)
    resolved = out.strip()
    if code != 0 or not (resolved == wd or resolved.startswith(wd + "/")):
        return None, f"ERROR: path '{path}' is outside {wd}"
    return resolved, None


# ------------------------------------------------------------- read tools
@tool(context=True)
async def read_file(tool_context: ToolContext, path: str, start: int = 1, end: int = 0) -> str:
    """Read a text file with line numbers. Optionally limit to lines start..end (end=0 means to the end)."""
    p, err = await _resolve(tool_context, path)
    if err:
        return err
    rng = f"{max(start, 1)},{end}p" if end else f"{max(start, 1)},$p"
    code, out = await _run(tool_context, f"set -o pipefail; nl -ba -w6 -s'| ' {shlex.quote(p)} | sed -n '{rng}'")
    return out if code == 0 else f"ERROR: {out}"


@tool(context=True)
async def list_dir(tool_context: ToolContext, path: str = ".") -> str:
    """List files and folders in a directory inside the workspace."""
    p, err = await _resolve(tool_context, path)
    if err:
        return err
    code, out = await _run(tool_context, f"ls -la {shlex.quote(p)}")
    return out if code == 0 else f"ERROR: {out}"


@tool(context=True)
async def find_files(tool_context: ToolContext, name_pattern: str, path: str = ".") -> str:
    """Find files by name pattern (e.g. '*.py', 'test_*.py'). Skips .git and node_modules."""
    p, err = await _resolve(tool_context, path)
    if err:
        return err
    cmd = (
        f"find {shlex.quote(p)} -type f -name {shlex.quote(name_pattern)} "
        "-not -path '*/.git/*' -not -path '*/node_modules/*' | head -200"
    )
    return (await _run(tool_context, cmd))[1] or "(no matches)"


@tool(context=True)
async def grep_search(tool_context: ToolContext, pattern: str, path: str = ".") -> str:
    """Search file contents recursively for a text/regex pattern. Returns file:line:match (max 200 lines)."""
    p, err = await _resolve(tool_context, path)
    if err:
        return err
    cmd = (
        "grep -rnIE --exclude-dir=.git --exclude-dir=node_modules "
        f"-e {shlex.quote(pattern)} -- {shlex.quote(p)} | head -200"
    )
    return (await _run(tool_context, cmd))[1] or "(no matches)"


@tool(context=True)
async def git_status(tool_context: ToolContext) -> str:
    """Show git status (short format) of the workspace."""
    return (await _run(tool_context, "git status --short --branch"))[1] or "(clean)"


@tool(context=True)
async def git_diff(tool_context: ToolContext, path: str = "") -> str:
    """Show uncommitted changes (staged and unstaged). Optionally limit to one path."""
    target = ""
    if path:
        p, err = await _resolve(tool_context, path)
        if err:
            return err
        target = f"-- {shlex.quote(p)}"
    cmd = f"git add -N . 2>/dev/null; git diff HEAD {target} 2>/dev/null || git diff {target}"
    return (await _run(tool_context, cmd))[1] or "(no changes)"


@tool(context=True)
async def git_log(tool_context: ToolContext, n: int = 10) -> str:
    """Show the last n commits (one line each)."""
    return (await _run(tool_context, f"git log --oneline -n {int(n)}"))[1] or "(no commits)"


# ------------------------------------------------------------- test / git
@tool(context=True)
async def run_tests(tool_context: ToolContext, command: str = "pytest -q", timeout: int = 300) -> str:
    """Run the project's test command in the sandbox and return PASSED/FAILED plus output."""
    code, out = await _run(tool_context, command, timeout=timeout)
    return f"{'PASSED' if code == 0 else f'FAILED (exit {code})'}\n{out}"


@tool(context=True)
async def git_commit(tool_context: ToolContext, message: str) -> str:
    """Stage all changes and commit them. Only use after tests pass and the review is approved."""
    cmd = (
        "git rev-parse --git-dir >/dev/null 2>&1 || git init -q; "
        "git add -A && git -c user.name=agent -c user.email=agent@local "
        f"commit -m {shlex.quote(message)}"
    )
    code, out = await _run(tool_context, cmd)
    return out if code == 0 else f"ERROR: {out}"


# ----------------------------------------------------- shared documents
async def _read_doc(ctx: ToolContext, name: str, missing: str) -> str:
    try:
        return await ctx.agent.sandbox.read_text(f"{_wd(ctx)}/{name}")
    except Exception:  # noqa: BLE001
        return missing


async def _write_doc(ctx: ToolContext, name: str, content: str) -> str:
    try:
        await ctx.agent.sandbox.write_text(f"{_wd(ctx)}/{name}", content)
        return f"{name} saved."
    except Exception as e:  # noqa: BLE001
        return f"ERROR: {e}"


@tool(context=True)
async def plan_read(tool_context: ToolContext) -> str:
    """Read the shared task plan (PLAN.md)."""
    return await _read_doc(tool_context, "PLAN.md", "No plan yet.")


@tool(context=True)
async def plan_write(tool_context: ToolContext, content: str) -> str:
    """Overwrite the shared task plan (PLAN.md). Keep it a short markdown checklist; tick items as they finish."""
    return await _write_doc(tool_context, "PLAN.md", content)


@tool(context=True)
async def requirements_read(tool_context: ToolContext) -> str:
    """Read REQUIREMENTS.md (the approved app requirements from the user interview)."""
    return await _read_doc(tool_context, "REQUIREMENTS.md", "No REQUIREMENTS.md yet.")


@tool(context=True)
async def requirements_write(tool_context: ToolContext, content: str) -> str:
    """Write the app requirements (REQUIREMENTS.md) gathered from the interview. Overwrites the file."""
    return await _write_doc(tool_context, "REQUIREMENTS.md", content)


# ------------------------------------------------------- human-in-the-loop
@tool(context=True)
async def ask_user(tool_context: ToolContext, question: str, options: list[str] | None = None) -> str:
    """Ask the human ONE question and wait for the answer. Optionally give 2-4 suggested options.
    The swarm pauses until the human replies; the reply is returned as text."""
    name = "interview-" + hashlib.md5(question.encode()).hexdigest()[:8]
    answer = tool_context.interrupt(name, reason={"question": question, "options": options or []})
    return str(answer)
# -------------------------------------------------------------- web tools
@tool
def web_fetch(url: str) -> str:
    """Fetch a web page or docs URL (http/https) and return its text. Runs on the host, not in the sandbox."""
    if not url.startswith(("http://", "https://")):
        return "ERROR: only http(s) URLs are allowed"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "agent-swarm/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            return _trunc(r.read(500_000).decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        return f"ERROR: {e}"


# ------------------------------------------------- tool groups (for agents)
READ_TOOLS = [read_file, list_dir, find_files, grep_search, git_status, git_diff, git_log]
PLAN_TOOLS = [plan_read, plan_write]
REQ_TOOLS = [requirements_read]
TEST_TOOLS = [run_tests]
COMMIT_TOOLS = [git_commit]
HUMAN_TOOLS = [ask_user]
WEB_TOOLS = [web_fetch]
