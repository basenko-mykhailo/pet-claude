#!/usr/bin/env python3
"""Live view of a pipeline run: stage lines from pipeline.log interleaved with
what the current agent is doing (tool calls, short thoughts, denials, errors),
read from its stream-json log. Follows the newest agent log automatically and
exits a few seconds after the run prints its summary.

    watch.py <run dir> <worktree>
"""

from __future__ import annotations

import glob
import json
import os
import sys
import time

TTY = sys.stdout.isatty()
DIM, BOLD, RED, RESET = ("\033[2m", "\033[1m", "\033[31m", "\033[0m") if TTY else ("",) * 4


class Tail:
    """Yields complete new lines appended to a file since the last read."""

    def __init__(self, path: str):
        self.path, self.offset, self.buf = path, 0, b""

    def lines(self) -> list[str]:
        try:
            with open(self.path, "rb") as f:
                f.seek(self.offset)
                chunk = f.read()
        except FileNotFoundError:
            return []
        self.offset += len(chunk)
        self.buf += chunk
        *done, self.buf = self.buf.split(b"\n")
        return [line.decode("utf-8", "replace") for line in done]


def one_line(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def describe(tool: str, args: dict, wt: str) -> str:
    def rel(p: str) -> str:
        return os.path.relpath(p, wt) if p.startswith(wt) else p

    if tool == "Bash":
        return one_line(args.get("command", "").replace(wt + "/", ""), 150)
    if tool in ("Read", "Edit", "Write", "NotebookEdit"):
        return rel(args.get("file_path", ""))
    if tool in ("Grep", "Glob"):
        where = args.get("path")
        return one_line(args.get("pattern", ""), 100) + (f"  in {rel(where)}" if where else "")
    if tool == "WebFetch":
        return args.get("url", "")
    if tool == "WebSearch":
        return args.get("query", "")
    if tool == "StructuredOutput":
        return "(final answer)"
    return one_line(json.dumps(args, ensure_ascii=False), 120)


def render(event: dict, wt: str) -> list[str]:
    out = []
    kind = event.get("type")
    if kind == "assistant":
        for block in event.get("message", {}).get("content", []):
            if block.get("type") == "tool_use":
                out.append(f"   🔧 {block.get('name')}  {DIM}{describe(block.get('name'), block.get('input') or {}, wt)}{RESET}")
            elif block.get("type") == "text" and block.get("text", "").strip():
                out.append(f"   💬 {DIM}{one_line(block['text'], 200)}{RESET}")
    elif kind == "user":
        for block in event.get("message", {}).get("content", []) or []:
            if isinstance(block, dict) and block.get("type") == "tool_result" and block.get("is_error"):
                content = block.get("content")
                if isinstance(content, list):
                    content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
                out.append(f"   {RED}⚠ {one_line(content or '', 180)}{RESET}")
    return out


def main() -> None:
    run, wt = sys.argv[1].rstrip("/"), sys.argv[2].rstrip("/")
    print(f"{BOLD}watching {run}{RESET}  (Ctrl-C to stop)\n")
    log = Tail(os.path.join(run, "pipeline.log"))
    agent, finished_at = None, None

    while True:
        for line in log.lines():
            print(f"{BOLD}{line}{RESET}" if "▶" in line or "===" in line else line, flush=True)
            if line.startswith("=== Run"):
                finished_at = time.time()

        logs = glob.glob(os.path.join(run, "*", "*.jsonl"))
        newest = max(logs, key=os.path.getmtime) if logs else None
        if newest and (agent is None or newest != agent.path):
            if agent:
                for line in agent.lines():  # drain the previous agent first
                    try:
                        for out in render(json.loads(line), wt):
                            print(out, flush=True)
                    except json.JSONDecodeError:
                        pass
            agent = Tail(newest)
            print(f"{DIM}   ── {os.path.relpath(newest, run)} ──{RESET}", flush=True)

        if agent:
            for line in agent.lines():
                try:
                    for out in render(json.loads(line), wt):
                        print(out, flush=True)
                except json.JSONDecodeError:
                    pass

        if finished_at and time.time() - finished_at > 3:
            return
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
