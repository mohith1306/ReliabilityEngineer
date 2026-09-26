#!/usr/bin/env python
"""BRE cockpit -- one screen of ground truth about this project.

Reads git, the session ledger, the stage tracker, the last test run and the submission
checklist, then runs structural integrity checks. It answers "where are we, is anything
broken, what is next" without opening ten files -- for a human, or for an agent starting
a fresh session (run this first, then /catch-up for the *why*).

    python scripts/cockpit.py              # the screen
    python scripts/cockpit.py --tests      # also run pytest and record the result
    python scripts/cockpit.py --json       # machine-readable
    python scripts/cockpit.py --write      # also refresh docs/STATUS.md

Stdlib only, on purpose: it must still run when the project itself is broken.
Nothing here mutates the repo except `--write` (docs/STATUS.md) and `--tests`
(runs/cockpit/last_tests.json, which is gitignored).
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
STAGES_MD = DOCS / "stages" / "STAGES.md"
INDEX_MD = DOCS / "memory" / "INDEX.md"
SESSIONS = DOCS / "memory" / "sessions"
CHECKLIST_MD = DOCS / "submission" / "CHECKLIST.md"
LAST_TESTS = ROOT / "runs" / "cockpit" / "last_tests.json"
STATUS_MD = DOCS / "STATUS.md"

# lablab.ai IBM Bob 2.0 Hackathon: Sep 27 2026 11:00 AM EDT (UTC-4) == 20:30 IST.
DEADLINE = datetime(2026, 9, 27, 11, 0, tzinfo=timezone(timedelta(hours=-4)))
WIDTH = 78


# ── helpers ──────────────────────────────────────────────────────────────────


def sh(*cmd: str, cwd: Path = ROOT, timeout: int = 60) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or "").strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, str(exc)


def bar(done: int, total: int, width: int = 12) -> str:
    if total <= 0:
        return "." * width
    filled = round(width * done / total)
    return "#" * filled + "." * (width - filled)


def fmt_delta(td: timedelta) -> str:
    secs = int(td.total_seconds())
    sign = "-" if secs < 0 else ""
    secs = abs(secs)
    return f"{sign}{secs // 3600}h {secs % 3600 // 60:02d}m"


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


# ── collectors ───────────────────────────────────────────────────────────────


def collect_clock() -> dict:
    now = datetime.now(timezone.utc).astimezone()
    return {
        "now": now.strftime("%a %Y-%m-%d %H:%M %Z"),
        "deadline": DEADLINE.astimezone().strftime("%a %Y-%m-%d %H:%M %Z")
        + "  (11:00 AM EDT)",
        "remaining": fmt_delta(DEADLINE - now),
        "expired": DEADLINE <= now,
    }


def collect_git() -> dict:
    g: dict = {}
    _, g["branch"] = sh("git", "rev-parse", "--abbrev-ref", "HEAD")
    _, g["head"] = sh("git", "rev-parse", "--short", "HEAD")
    _, g["subject"] = sh("git", "log", "-1", "--format=%s")
    rc, up = sh("git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    g["upstream"] = up if rc == 0 else None
    if g["upstream"]:
        rc, lr = sh("git", "rev-list", "--left-right", "--count", f"{g['upstream']}...HEAD")
        if rc == 0:
            behind, ahead = lr.split()
            g["behind_upstream"], g["ahead_upstream"] = int(behind), int(ahead)
    rc, lr = sh("git", "rev-list", "--left-right", "--count", "origin/main...HEAD")
    if rc == 0:
        behind, ahead = lr.split()
        g["behind_main"], g["ahead_main"] = int(behind), int(ahead)
    _, g["origin_main"] = sh("git", "rev-parse", "--short", "origin/main")
    g["main_contained"] = sh("git", "merge-base", "--is-ancestor", "origin/main", "HEAD")[0] == 0
    _, status = sh("git", "status", "--porcelain")
    g["dirty_files"] = len([line for line in status.splitlines() if line.strip()])
    g["merge_in_progress"] = (ROOT / ".git" / "MERGE_HEAD").exists()
    return g


def collect_stages() -> list[dict]:
    text = read(STAGES_MD)
    rows = {}
    for m in re.finditer(
        r"^\|\s*(S\d+)\s*\|\s*(.+?)\s*\|\s*(.*?)\s*\|\s*`?(NOT_STARTED|IN_PROGRESS|BLOCKED|DONE)`?\s*\|",
        text, re.M,
    ):
        rows[m.group(1)] = {"id": m.group(1), "name": m.group(2), "status": m.group(4)}
    # criteria live under "### Sx — ..." headings
    parts = re.split(r"^### (S\d+) — .*$", text, flags=re.M)
    for i in range(1, len(parts), 2):
        sid, body = parts[i], parts[i + 1]
        # stop at the next H2 so the stage log is not miscounted
        body = re.split(r"^## ", body, flags=re.M)[0]
        done = len(re.findall(r"^- \[x\]", body, re.M | re.I))
        todo = len(re.findall(r"^- \[ \]", body, re.M))
        if sid in rows:
            rows[sid]["done"], rows[sid]["total"] = done, done + todo
    for r in rows.values():
        r.setdefault("done", 0)
        r.setdefault("total", 0)
    return [rows[k] for k in sorted(rows, key=lambda s: int(s[1:]))]


def collect_position() -> dict:
    text = read(STAGES_MD)
    out = {}
    for key in ("Current stage", "Blocked on", "Sharpest risk"):
        m = re.search(rf"\*\*{key}\*\*\s*\|\s*(.+?)\s*\|", text)
        out[key] = m.group(1) if m else "?"
    return out


def collect_ledger() -> dict:
    text = read(INDEX_MD)
    sessions = []
    for m in re.finditer(
        r"^\|\s*\[(\d{4})\]\(([^)]+)\)\s*\|\s*([\d-]+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(\S+)\s*\|\s*(\S+)\s*\|",
        text, re.M,
    ):
        sessions.append({"n": m.group(1), "file": m.group(2), "date": m.group(3),
                         "title": m.group(4), "author": m.group(5), "stage": m.group(6),
                         "status": m.group(7)})
    threads = []
    tail = text.split("## Open threads", 1)[-1]
    for m in re.finditer(r"^\|\s*(\d{4})\s*\|\s*#(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$", tail, re.M):
        clean = lambda x: re.sub(r"[*`]", "", x)  # noqa: E731
        threads.append({"ref": f"{m.group(1)}#{m.group(2)}", "text": clean(m.group(3)), "owner": clean(m.group(4))})
    return {"sessions": sessions, "threads": threads}


def collect_submission() -> list[dict]:
    items = []
    for m in re.finditer(
        r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(DONE|DRAFTED|TODO|HUMAN|BLOCKED)\s*\|\s*(.*?)\s*\|\s*$",
        read(CHECKLIST_MD), re.M,
    ):
        items.append({"n": int(m.group(1)), "item": m.group(2), "owner": m.group(3),
                      "status": m.group(4), "notes": m.group(5)})
    return items


def collect_tests(run: bool) -> dict:
    if run:
        py = sys.executable
        # No -q here: pytest.ini already passes it, and -qq drops the summary line.
        rc, out = sh(py, "-m", "pytest", "-p", "no:warnings", "--tb=no", "-rfE", timeout=900)
        summary = next((ln for ln in reversed(out.splitlines())
                        if re.search(r"\d+ (passed|failed|error)", ln)), "")
        counts = {k: 0 for k in ("passed", "failed", "skipped", "xfailed", "xpassed", "error")}
        for k in counts:
            m = re.search(rf"(\d+) {k}", summary)
            if m:
                counts[k] = int(m.group(1))
        _, head = sh("git", "rev-parse", "--short", "HEAD")
        _, dirty = sh("git", "status", "--porcelain")
        rec = {"ts": datetime.now(timezone.utc).isoformat(), "sha": head,
               "dirty": bool(dirty.strip()), "exit": rc, "parsed": bool(summary), **counts,
               "failures": [ln for ln in out.splitlines() if ln.startswith(("FAILED", "ERROR"))][:12]}
        LAST_TESTS.parent.mkdir(parents=True, exist_ok=True)
        LAST_TESTS.write_text(json.dumps(rec, indent=2), encoding="utf-8")
        return rec
    try:
        return json.loads(LAST_TESTS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


# ── integrity checks ─────────────────────────────────────────────────────────


def check_integrity(stages: list[dict], ledger: dict, git: dict) -> list[dict]:
    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str = "", warn: bool = False) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail, "warn": warn and not ok})

    # 1. conflict markers
    rc, out = sh("git", "grep", "-l", "-E", r"^(<<<<<<< |>>>>>>> )", "--", "*.py", "*.md", "*.json")
    add("no merge-conflict markers", rc != 0, out.replace("\n", ", "))
    add("no merge left half-finished", not git.get("merge_in_progress"), "MERGE_HEAD present")

    # 2. ledger <-> files
    files = sorted(p.name for p in SESSIONS.glob("*.md"))
    nums = [f[:4] for f in files]
    dupes = sorted({n for n in nums if nums.count(n) > 1})
    add("session numbers unique", not dupes, f"duplicated: {', '.join(dupes)}")
    idx = {s["n"] for s in ledger["sessions"]}
    missing = sorted(set(nums) - idx)
    ghost = sorted(idx - set(nums))
    add("every session file has an INDEX row", not missing, f"missing: {', '.join(missing)}")
    add("every INDEX row has a session file", not ghost, f"no file: {', '.join(ghost)}")
    bad_fm = []
    for f in files:
        m = re.search(r"^session:\s*(\d{4})", read(SESSIONS / f), re.M)
        if not m or m.group(1) != f[:4]:
            bad_fm.append(f)
    add("session front-matter matches filename", not bad_fm, ", ".join(bad_fm))
    open_sessions = [s["n"] for s in ledger["sessions"] if s["status"] not in ("closed", "abandoned")]
    add("no session left open", not open_sessions, f"open: {', '.join(open_sessions)}", warn=True)

    # 3. stage tracker vs its own criteria
    lies = [f"{s['id']} DONE but {s['total'] - s['done']} criteria unchecked"
            for s in stages if s["status"] == "DONE" and s["done"] < s["total"]]
    add("no DONE stage has unchecked criteria", not lies, "; ".join(lies))
    idle = [f"{s['id']} all criteria met but status {s['status']}"
            for s in stages if s["total"] and s["done"] == s["total"] and s["status"] != "DONE"]
    add("no finished stage left un-DONE", not idle, "; ".join(idle), warn=True)

    # 4. doc links resolve
    broken = []
    for md in [*DOCS.rglob("*.md"), ROOT / "README.md", ROOT / "CLAUDE.md"]:
        text = re.sub(r"```.*?```", "", read(md), flags=re.S)
        for m in re.finditer(r"\]\((?!https?:|#|mailto:)([^)#\s]+)", text):
            if not (md.parent / m.group(1)).exists():
                broken.append(f"{md.relative_to(ROOT).as_posix()} -> {m.group(1)}")
    add("doc links resolve", not broken, f"{len(broken)} broken, e.g. " + "; ".join(broken[:3]))

    # 5. declared dependencies installed (this is what would have caught `websockets`)
    absent = []
    for line in read(ROOT / "requirements.txt").splitlines():
        name = re.split(r"[<>=!~\[ ]", line.strip(), maxsplit=1)[0]
        if not name or name.startswith("#"):
            continue
        try:
            importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            absent.append(name)
    add("requirements.txt all installed", not absent, f"missing in this interpreter: {', '.join(absent)}")

    # 6. hygiene: no secrets, no local state tracked
    rc, out = sh("git", "grep", "-n", "-I", "-E",
                 r"(BOB_API_KEY\s*[=:]\s*['\"]?[A-Za-z0-9_-]{24,}|sk-[A-Za-z0-9]{24,}|ghp_[A-Za-z0-9]{30,})")
    add("no API keys committed", rc != 0, out.splitlines()[0][:100] if out else "")
    _, tracked = sh("git", "ls-files")
    local = [f for f in tracked.splitlines()
             if f.endswith((".db", ".sqlite3")) or f == ".env" or f.startswith("runs/")]
    add("no local state tracked (*.db, .env, runs/)", not local, ", ".join(local))
    return checks


# ── next actions ─────────────────────────────────────────────────────────────


def derive_next(data: dict) -> list[str]:
    nxt: list[str] = []
    bad = [c for c in data["integrity"] if not c["ok"] and not c["warn"]]
    if bad:
        nxt.append(f"FIX INTEGRITY FIRST: {', '.join(c['name'] for c in bad)}")
    t = data["tests"]
    if t and (t.get("failed") or t.get("error") or not t.get("passed")):
        nxt.append(f"Tests are red at {t.get('sha')}: {t.get('failed', 0)} failed, {t.get('error', 0)} errors")
    if data["git"].get("merge_in_progress"):
        nxt.append("A merge is half-finished -- resolve and commit it")
    stage = next((s for s in data["stages"] if s["status"] in ("IN_PROGRESS",)), None) or \
        next((s for s in data["stages"] if s["status"] == "NOT_STARTED"), None)
    if stage:
        nxt.append(f"Build {stage['id']} - {stage['name']} ({stage['done']}/{stage['total']} criteria)")
    human = [i for i in data["submission"] if i["status"] in ("HUMAN", "BLOCKED")]
    if human:
        nxt.append("Needs a person: " + "; ".join(f"#{i['n']} {i['item']}" for i in human))
    g = data["git"]
    if g.get("ahead_main") and (not g.get("upstream") or g.get("ahead_upstream")):
        nxt.append(f"{g['ahead_main']} commit(s) ahead of origin/main exist only locally -- "
                   "the judged repo does not have them until someone pushes/merges")
    return nxt


# ── render ───────────────────────────────────────────────────────────────────


def render(data: dict) -> str:
    L: list[str] = []
    hr = "-" * WIDTH

    def h(title: str) -> None:
        L.append("")
        L.append(f"== {title} " + "=" * max(0, WIDTH - len(title) - 4))

    c = data["clock"]
    L.append("BRE COCKPIT".ljust(WIDTH - 24) + c["now"])
    h("CLOCK")
    L.append(f"deadline  {c['deadline']}")
    L.append(f"remaining {'DEADLINE PASSED' if c['expired'] else c['remaining']}")

    g = data["git"]
    h("GIT")
    L.append(f"branch    {g['branch']} @ {g['head']}  {g['subject'][:52]}")
    if "behind_main" in g:
        L.append(f"vs main   {g['ahead_main']} ahead / {g['behind_main']} behind origin/main ({g['origin_main']})"
                 + ("" if g["main_contained"] else "   <-- origin/main is NOT contained in this branch"))
    if g.get("upstream"):
        L.append(f"upstream  {g['upstream']}: {g.get('ahead_upstream', 0)} unpushed, {g.get('behind_upstream', 0)} to pull")
    else:
        L.append("upstream  (none -- this branch exists only locally)")
    L.append(f"worktree  {g['dirty_files']} uncommitted path(s)" + ("   MERGE IN PROGRESS" if g["merge_in_progress"] else ""))

    h("STAGES")
    for s in data["stages"]:
        L.append(f"{s['id']:<3} {s['status']:<12} {bar(s['done'], s['total'])} {s['done']:>2}/{s['total']:<2} {s['name'][:38]}")
    pos = data["position"]
    L.append(hr)
    L.append(f"current   {pos['Current stage'][:66]}")
    L.append(f"blocked   {pos['Blocked on'][:66]}")
    L.append(f"risk      {pos['Sharpest risk'][:66]}")

    h("TESTS")
    t = data["tests"]
    if not t:
        L.append("no recorded run -- `python scripts/cockpit.py --tests`")
    else:
        stale = "" if t.get("sha") == g["head"] and not g["dirty_files"] else "   (stale: code changed since)"
        if not t.get("parsed", True) or not t.get("passed"):
            verdict = "UNKNOWN"  # a run that reports no passes proves nothing
        elif t.get("failed") or t.get("error") or t.get("exit") != 0:
            verdict = "RED"
        else:
            verdict = "GREEN"
        L.append(f"{verdict}  {t.get('passed', 0)} passed, {t.get('failed', 0)} failed, {t.get('error', 0)} errors, "
                 f"{t.get('skipped', 0)} skipped, {t.get('xfailed', 0)} xfailed @ {t.get('sha')}{stale}")
        for f in t.get("failures", [])[:5]:
            L.append(f"  {f[:WIDTH - 2]}")

    h("SUBMISSION (lablab.ai)")
    sub = data["submission"]
    counts: dict[str, int] = {}
    for i in sub:
        counts[i["status"]] = counts.get(i["status"], 0) + 1
    L.append("  ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "no checklist")
    for i in sub:
        L.append(f"  {i['n']:>2} {i['status']:<8} {i['owner']:<11} {i['item'][:44]}")

    h("OPEN THREADS")
    for th in data["ledger"]["threads"]:
        L.append(f"{th['ref']:<7} [{th['owner'][:18]}] {th['text'][:WIDTH - 32]}")
    L.append(hr)
    L.append("last sessions: " + " | ".join(f"{s['n']} {s['title'][:22]}" for s in data["ledger"]["sessions"][-3:]))

    h("INTEGRITY")
    ok = sum(1 for x in data["integrity"] if x["ok"])
    L.append(f"{ok}/{len(data['integrity'])} checks pass")
    for x in data["integrity"]:
        if not x["ok"]:
            L.append(f"  {'WARN' if x['warn'] else 'FAIL'}  {x['name']}: {x['detail'][:WIDTH - 12]}")

    h("NEXT")
    for i, n in enumerate(data["next"], 1):
        L.append(f"{i}. {n[:WIDTH - 4]}")
    return "\n".join(L)


# ── main ─────────────────────────────────────────────────────────────────────


def build(run_tests: bool) -> dict:
    stages = collect_stages()
    ledger = collect_ledger()
    git = collect_git()
    data = {
        "clock": collect_clock(),
        "git": git,
        "stages": stages,
        "position": collect_position(),
        "ledger": ledger,
        "submission": collect_submission(),
        "tests": collect_tests(run_tests),
        "integrity": check_integrity(stages, ledger, git),
    }
    data["next"] = derive_next(data)
    return data


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tests", action="store_true", help="run pytest and record the result")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of the screen")
    ap.add_argument("--write", action="store_true", help="also refresh docs/STATUS.md")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    data = build(args.tests)
    screen = render(data)
    print(json.dumps(data, indent=2) if args.json else screen)

    if args.write:
        STATUS_MD.write_text(
            "# Project status\n\n"
            "> **Generated** by `python scripts/cockpit.py --write` at "
            f"{data['clock']['now']}, commit `{data['git']['head']}`. Do not edit by hand -- "
            "it is regenerated from git, the ledger, the stage tracker and the last test run. "
            "For the *why*, read `docs/memory/INDEX.md`.\n\n```text\n" + screen + "\n```\n",
            encoding="utf-8",
        )
    failed = [c for c in data["integrity"] if not c["ok"] and not c["warn"]]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
