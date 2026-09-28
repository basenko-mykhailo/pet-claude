#!/usr/bin/env python3
"""File-backed task queue for the agentic pipeline.

Each task is a Markdown spec whose YAML front-matter carries the queue state:

    ---
    id: 6.2
    status: todo
    depends_on: [6.1]
    ---

`status` is todo | done | needs-human; the pipeline adds `reason:` for
needs-human. No inline comments — values are taken verbatim.

The spec's first heading (`# <anything> — Title`) gives the title. The progress
log (implementations_progress.md) is a human view that `progress` rewrites.

This module is the only thing that knows the storage format, so it can later be
swapped for GitHub Issues without touching the orchestrator.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys

READY_DEPS = {"done"}
STUCK = {"needs-human"}


def id_key(task_id: str) -> tuple:
    return tuple(int(p) if p.isdigit() else p for p in task_id.split("."))


class Task:
    def __init__(self, path: str, root: str):
        self.path = path
        self.rel = os.path.relpath(path, root)
        with open(path, encoding="utf-8") as f:
            self.text = f.read()
        self.meta, self.body = self._split(self.text)
        self.id = str(self.meta.get("id", "")).strip()
        if not self.id:
            raise SystemExit(f"taskq: {self.rel} has no `id` in front-matter")

    @staticmethod
    def _split(text: str):
        if not text.startswith("---\n"):
            return {}, text
        end = text.find("\n---\n", 4)
        if end == -1:
            return {}, text
        meta = {}
        for line in text[4:end].splitlines():
            if ":" not in line or line.lstrip().startswith("#"):
                continue
            key, _, value = line.partition(":")
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                value = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
            else:
                value = value.strip("'\"")
            meta[key.strip()] = value
        return meta, text[end + 5 :]

    @property
    def status(self) -> str:
        return self.meta.get("status", "todo") or "todo"

    @property
    def deps(self) -> list[str]:
        deps = self.meta.get("depends_on", [])
        return deps if isinstance(deps, list) else [deps] if deps else []

    @property
    def title(self) -> str:
        m = re.search(r"^# .*?\s[—-]\s(.+)$", self.body, re.M)
        return m.group(1).strip() if m else self.id

    def set(self, key: str, value: str) -> None:
        self.meta[key] = value
        lines = []
        for k, v in self.meta.items():
            if isinstance(v, list):
                v = "[" + ", ".join(v) + "]"
            lines.append(f"{k}: {v}".rstrip())
        self.text = "---\n" + "\n".join(lines) + "\n---\n" + self.body
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(self.text)


class Queue:
    def __init__(self, root: str, pattern: str):
        self.root = root
        paths = glob.glob(os.path.join(root, pattern))
        self.tasks = sorted((Task(p, root) for p in paths), key=lambda t: id_key(t.id))
        self.by_id = {t.id: t for t in self.tasks}

    def get(self, task_id: str) -> Task:
        if task_id not in self.by_id:
            raise SystemExit(f"taskq: unknown task {task_id}")
        return self.by_id[task_id]

    def ready(self) -> list[Task]:
        return [
            t for t in self.tasks
            if t.status == "todo" and all(self._dep_status(d) in READY_DEPS for d in t.deps)
        ]

    def blocked(self) -> list[tuple[Task, str]]:
        """Todo tasks that can never become ready in this run (a dep is stuck)."""
        out = []
        for t in self.tasks:
            if t.status != "todo":
                continue
            culprit = self._stuck_dep(t, set())
            if culprit:
                out.append((t, culprit))
        return out

    def _dep_status(self, dep: str) -> str:
        return self.by_id[dep].status if dep in self.by_id else "done"  # deps outside the glob are assumed done

    def _stuck_dep(self, t: Task, seen: set) -> str | None:
        for d in t.deps:
            if d in seen or d not in self.by_id:
                continue
            seen.add(d)
            dep = self.by_id[d]
            if dep.status in STUCK:
                return d
            if dep.status == "todo":
                inner = self._stuck_dep(dep, seen)
                if inner:
                    return inner
        return None


EMOJI = {"todo": "⬜", "done": "✅", "partial": "🟡", "needs-human": "🛑"}


def update_progress(root: str, progress_rel: str, q: Queue, task: Task, emoji: str, text: str, spec_label: str) -> None:
    path = os.path.join(root, progress_rel)
    with open(path, encoding="utf-8") as f:
        content = f.read()
    text = " ".join(text.split())
    line = f"- {emoji} **{task.id} {task.title}** — {text} {spec_label}: `{task.rel}`."
    pattern = re.compile(rf"^- \S+ \*\*{re.escape(task.id)} .*$", re.M)
    if pattern.search(content):
        content = pattern.sub(lambda _: line, content, count=1)
    else:
        content = content.rstrip("\n") + "\n" + line + "\n"

    # Epic row in the summary table: ✅ when every task is done, 🟡 once anything moved.
    epic = task.id.split(".")[0]
    statuses = [t.status for t in q.tasks]
    epic_emoji = "✅" if all(s == "done" for s in statuses) else "🟡" if any(s != "todo" for s in statuses) else "⬜"
    content = re.sub(
        rf"^(\| {re.escape(epic)} \|.*\| )\S+( \|)$",
        lambda m: m.group(1) + epic_emoji + m.group(2),
        content,
        count=1,
        flags=re.M,
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", required=True, help="checkout the globs are relative to")
    ap.add_argument("--glob", required=True, help="task spec glob, e.g. docs/tickets/epic-6/task-*.md (relative to --root)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="TSV: id, status, deps, title, path")
    sub.add_parser("next", help="id of the first ready task (empty if none)")
    sub.add_parser("blocked", help="TSV: id, stuck dependency")
    sub.add_parser("table", help="Markdown status table")
    g = sub.add_parser("get")
    g.add_argument("id")
    g.add_argument("field", choices=["path", "title", "status", "reason"])
    s = sub.add_parser("set")
    s.add_argument("id")
    s.add_argument("key")
    s.add_argument("value")
    p = sub.add_parser("progress", help="rewrite the task's line in the progress log")
    p.add_argument("id")
    p.add_argument("state", choices=list(EMOJI))
    p.add_argument("text")
    p.add_argument("--file", required=True)
    p.add_argument("--spec-label", default="Spec", help="label before the spec path, in the log's language")
    args = ap.parse_args()

    q = Queue(args.root, args.glob)
    if args.cmd == "list":
        for t in q.tasks:
            print("\t".join([t.id, t.status, ",".join(t.deps), t.title, t.rel]))
    elif args.cmd == "next":
        ready = q.ready()
        if ready:
            print(ready[0].id)
    elif args.cmd == "blocked":
        for t, dep in q.blocked():
            print(f"{t.id}\t{dep}")
    elif args.cmd == "table":
        print("| Задача | Статус | Примітка |\n|---|---|---|")
        for t in q.tasks:
            note = t.meta.get("reason", "").replace("|", "/") if t.status == "needs-human" else ""
            print(f"| {t.id} {t.title} | {EMOJI.get(t.status, t.status)} {t.status} | {note} |")
    elif args.cmd == "get":
        t = q.get(args.id)
        print({"path": t.rel, "title": t.title, "status": t.status, "reason": t.meta.get("reason", "")}[args.field])
    elif args.cmd == "set":
        q.get(args.id).set(args.key, " ".join(args.value.split()))
    elif args.cmd == "progress":
        update_progress(args.root, args.file, q, q.get(args.id), EMOJI[args.state], args.text, args.spec_label)


if __name__ == "__main__":
    sys.exit(main())
