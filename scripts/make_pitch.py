#!/usr/bin/env python
"""Build the pitch deck: docs/submission/BRE_pitch.html  (self-contained, 16:9, exports to PDF)

    python scripts/make_pitch.py

Open the HTML in a browser (arrow keys / click to navigate). To submit a PDF: Ctrl+P -> Save as PDF, landscape,
margins none, "background graphics" on -> one slide per page.

Every number on the results slide is read from the stamped artifacts in docs/artifacts/, so the deck cannot quote a
figure the data does not support. Yellow `.todo` boxes mark sentences a person must update before submitting.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "docs" / "artifacts"
OUT = ROOT / "docs" / "submission" / "BRE_pitch.html"


def latest(pattern):
    """Timestamp-anchored: `comparison_full_*.json` must not also match `comparison_full_tau_from_recurring_*.json`."""
    stem, _, tail = pattern.partition("*")
    rx = re.compile(re.escape(stem) + r"\d{8}T\d{6}Z" + re.escape(tail) + "$")
    files = sorted(f for f in ART.glob(pattern) if rx.match(f.name))
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else None


def agg(d, arm, key):
    return d["result"]["aggregate"][arm][key]["mean"]


def result_card(slice_name, title, sub):
    d = latest(f"comparison_{slice_name}_*.json")
    if not d:
        return f'<div class="card"><h4>{html.escape(title)}</h4><p class="muted">artifact missing — run the comparison</p></div>'
    base, bre = agg(d, "baseline", "tokens_per_incident"), agg(d, "bre", "tokens_per_incident")
    delta = (bre - base) / base * 100 if base else 0
    served, refuted, wasted = agg(d, "bre", "memory_diagnoses"), agg(d, "bre", "memory_refuted"), agg(d, "bre", "wasted_attempts")
    res = agg(d, "bre", "resolution_rate") * 100
    sign = "−" if delta < 0 else "+"
    color = "var(--green)" if delta < -0.5 else "var(--amber)" if abs(delta) <= 0.5 else "var(--red)"
    return f"""<div class="card">
  <h4>{html.escape(title)}</h4><p class="muted small">{html.escape(sub)}</p>
  <div class="big" style="color:{color}">{sign}{abs(delta):.1f}%</div><div class="muted small">nominal cost / incident vs Bob alone</div>
  <table class="mini"><tr><td>from verified memory</td><td><b>{served:.0f}</b> of {d['corpus_size']}</td></tr>
  <tr><td>refuted by the tests</td><td><b>{refuted:.0f}</b></td></tr>
  <tr><td>wasted attempts</td><td><b>{wasted:.0f}</b></td></tr>
  <tr><td>resolved</td><td><b>{res:.0f}%</b> (same as Bob alone)</td></tr></table>
  <div class="muted xs">τ {d['tau']} · {d['orderings']} orderings · {d['look_alikes_in_corpus']} look-alikes</div></div>"""


def main() -> int:
    cards = "".join([
        result_card("recurring", "Failures that recur", "no look-alikes"),
        result_card("full", "With look-alike twins", "τ tuned on this corpus"),
        result_card("full_tau_from_recurring", "Out of distribution", "τ tuned without look-alikes"),
    ])
    val = latest("simulator_validation_*.json") or {}
    validation = f"{val.get('agree', '?')} of {val.get('of', '?')}"

    page = TEMPLATE.replace("{{CARDS}}", cards).replace("{{VALIDATION}}", validation)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8", newline="\n")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
    return 0


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bob Reliability Engineer — pitch</title>
<style>
  :root { --bg:#0e1116; --panel:#161b22; --line:#2b3440; --text:#e9eef5; --muted:#93a1b3; --accent:#6ea0ff; --violet:#b394ff;
          --green:#4cc38a; --amber:#f0b04a; --red:#ff8a92; }
  * { box-sizing:border-box; margin:0; }
  html,body { height:100%; background:#05070a; color:var(--text); font-family: "Segoe UI", system-ui, -apple-system, Roboto, sans-serif; }
  #stage { position:fixed; inset:0; display:grid; place-items:center; overflow:hidden; }
  .slide { width:1280px; height:720px; padding:56px 72px; position:absolute; transform-origin:center; display:none;
           background: radial-gradient(900px 500px at 88% 10%, #2a2f7a55, transparent), linear-gradient(160deg,#0e1116,#151233); }
  .slide.on { display:flex; flex-direction:column; }
  .kicker { color:var(--accent); font-weight:700; letter-spacing:.14em; text-transform:uppercase; font-size:16px; margin-bottom:14px; }
  h1 { font-size:88px; line-height:1.02; letter-spacing:-.02em; } h2 { font-size:46px; line-height:1.12; letter-spacing:-.015em; margin-bottom:26px; }
  h3 { font-size:26px; margin-bottom:8px; } h4 { font-size:22px; margin-bottom:4px; }
  p, li { font-size:24px; line-height:1.45; } .muted { color:var(--muted); } .small { font-size:18px; } .xs { font-size:14px; }
  .accent { color:var(--accent); } .green{color:var(--green)} .amber{color:var(--amber)} .red{color:var(--red)} .violet{color:var(--violet)}
  .row { display:flex; gap:28px; } .col { flex:1; } .grow{flex:1} .center{align-items:center;justify-content:center}
  .card { background:#161b22cc; border:1px solid var(--line); border-radius:16px; padding:24px 26px; flex:1; }
  .big { font-size:66px; font-weight:800; letter-spacing:-.03em; line-height:1.05; margin-top:10px; }
  table { border-collapse:collapse; width:100%; } th,td { text-align:left; padding:9px 12px; border-bottom:1px solid var(--line); font-size:20px; vertical-align:top; }
  th { color:var(--muted); font-size:14px; letter-spacing:.08em; text-transform:uppercase; }
  table.mini td { font-size:17px; padding:5px 0; border-bottom:1px solid #2b344066; } table.mini td:last-child{text-align:right}
  .pill { display:inline-block; padding:3px 12px; border-radius:999px; font-size:16px; font-weight:700; border:1px solid currentColor; margin-right:8px; }
  code { font-family:ui-monospace,Consolas,monospace; background:#0b0f14; padding:2px 8px; border-radius:6px; font-size:.85em; }
  .todo { background:#f0b04a22; border:2px dashed var(--amber); color:var(--amber); padding:10px 16px; border-radius:10px; font-size:18px; margin-top:14px; }
  .steps { display:flex; gap:12px; margin-top:6px; } .step { flex:1; background:#161b22cc; border:1px solid var(--line); border-radius:14px; padding:16px; }
  .step .n { color:var(--muted); font-weight:700; font-size:14px; } .step p { font-size:18px; line-height:1.35; margin-top:6px; }
  .foot { margin-top:auto; display:flex; justify-content:space-between; color:var(--muted); font-size:14px; }
  ul { padding-left:26px; } li { margin-bottom:8px; }
  #hint { position:fixed; bottom:10px; right:14px; color:#5d6b7c; font-size:12px; }
  @media print {
    @page { size:1280px 720px; margin:0; }
    html,body { background:none; height:auto; } #stage { position:static; display:block; overflow:visible; } #hint{display:none}
    .slide { display:flex !important; flex-direction:column; position:relative; transform:none !important; page-break-after:always; break-after:page; }
  }
</style></head><body>
<div id="stage">

<!-- 1 -->
<section class="slide"><div class="kicker">IBM Bob 2.0 Hackathon · lablab.ai</div>
  <h1>Bob Reliability<br><span class="accent">Engineer</span></h1>
  <p style="margin-top:28px;font-size:36px">Don't just generate a fix.<br>Verify it — and learn who was right.</p>
  <div style="margin-top:34px"><span class="pill accent">evidence first</span><span class="pill amber">human-gated writes</span><span class="pill violet">branch + rollback</span><span class="pill green">real test verification</span></div>
  <div class="foot"><span>BRE orchestrates IBM Bob · it never reimplements it</span><span>github.com/mohith1306/ReliabilityEngineer</span></div></section>

<!-- 2 -->
<section class="slide"><div class="kicker">The problem</div>
  <h2>An agent can write a fix in minutes.<br><span class="muted">Then three questions nobody can answer.</span></h2>
  <div class="row" style="margin-top:8px">
    <div class="card"><h3 class="red">Was it right?</h3><p class="muted">A green CI run can be made green by deleting or skipping the test that was failing.</p></div>
    <div class="card"><h3 class="amber">Was it safe?</h3><p class="muted">Which branch did it touch? Who approved it? Can it be undone exactly, without eating someone's unsaved work?</p></div>
    <div class="card"><h3 class="green">Did we learn?</h3><p class="muted">The same outage recurs. Nobody remembers who diagnosed it correctly last time — or whether they were right.</p></div></div>
  <p style="margin-top:34px;font-size:28px">Today the answers are a gut feeling, a passing build that may be lying, and <b>nothing</b>.</p></section>

<!-- 3 -->
<section class="slide"><div class="kicker">The idea</div>
  <h2>A reliability layer <span class="accent">around</span> IBM Bob</h2>
  <div class="row grow" style="align-items:center">
  <svg viewBox="0 0 620 380" width="640" height="392" aria-label="the BRE loop">
    <g font-family="Segoe UI, sans-serif" font-size="17" font-weight="700" text-anchor="middle">
      <g stroke-width="3" fill="#0e1116">
        <circle cx="90" cy="60" r="48" stroke="#93a1b3"/><circle cx="230" cy="60" r="52" stroke="#6ea0ff"/><circle cx="380" cy="60" r="48" stroke="#6ea0ff"/><circle cx="530" cy="60" r="48" stroke="#6ea0ff"/>
        <circle cx="530" cy="240" r="52" stroke="#f0b04a"/><circle cx="380" cy="240" r="52" stroke="#b394ff"/><circle cx="230" cy="240" r="48" stroke="#4cc38a"/><circle cx="90" cy="240" r="48" stroke="#4cc38a"/></g>
      <g fill="#e9eef5"><text x="90" y="66" fill="#93a1b3">Detect</text><text x="230" y="66" fill="#6ea0ff">Investigate</text><text x="380" y="66" fill="#6ea0ff">Diagnose</text><text x="530" y="66" fill="#6ea0ff">Risk</text>
        <text x="530" y="246" fill="#f0b04a">Approve</text><text x="380" y="246" fill="#b394ff">Remediate</text><text x="230" y="246" fill="#4cc38a">Verify</text><text x="90" y="246" fill="#4cc38a">Learn</text></g>
      <g stroke="#2b3440" stroke-width="3" fill="none"><path d="M138 60H178M282 60H332M428 60H482M530 108V188M478 240H432M328 240H278M182 240H138"/></g>
      <path d="M230 188C230 130 230 118 230 112" stroke="#ff8a92" stroke-width="3" fill="none" stroke-dasharray="7 6"/>
      <text x="250" y="152" fill="#ff8a92" font-size="16" text-anchor="start">refuted? roll back · retry (capped)</text>
    </g></svg>
  <div class="col"><ul>
    <li>Bob <b>investigates and diagnoses read-only</b>; edits files only after a human approves</li>
    <li>The <b>real test suite</b> decides if a fix worked — not the model</li>
    <li>Wrong? <b>Rolled back exactly</b>, recorded as refuted, retried — and it <b>stops</b> at a cap</li>
    <li>Right? It becomes <b>verified memory</b> the next incident can reuse</li></ul></div></div></section>

<!-- 4 -->
<section class="slide"><div class="kicker">How IBM Bob is used</div>
  <h2>Bob does the engineering. BRE decides whether to trust it.</h2>
  <table><tr><th>BRE stage</th><th>Bob Shell mode</th><th>Can write?</th></tr>
    <tr><td>Investigate · diagnose</td><td><code>bob run --mode ask</code></td><td class="green">No — structurally read-only</td></tr>
    <tr><td>Plan a remediation</td><td><code>bob run --mode plan</code></td><td class="green">No</td></tr>
    <tr><td>Remediate</td><td><code>bob run --mode agent</code></td><td class="amber">Yes — only behind approval, allowlist, checkpoint, branch and diff guard</td></tr></table>
  <p class="small muted" style="margin-top:16px">Bob's own <code>stats</code> (tokens, cost, task id) are written into the outcome ledger on every call. One <code>allow_writes=True</code> exists in the codebase — asserted by an AST test.</p>
  <div class="todo"><b>TEAM — update before submitting:</b> live-Bob status. Today: integration built against Bob Shell's documented contract; demo runs a <b>labelled stand-in</b> ("SIMULATED BOB" on every screen). After Task A/B: "verified live on &lt;date&gt;; Bob task summaries in the repo."</div></section>

<!-- 5 -->
<section class="slide"><div class="kicker">Safety</div>
  <h2>The write path is a <span class="accent">safety argument</span>, not a feature</h2>
  <table>
    <tr><td><b>Analysis is free; mutation is privileged</b></td><td class="muted">read-only unless the repo is on an allowlist — deny by default</td></tr>
    <tr><td><b>A human approves, and who is on the record</b></td><td class="muted">identity comes from an API key, never request text; re-checked inside the engine</td></tr>
    <tr><td><b>Never on the default branch</b></td><td class="muted">pinned git checkpoint → fresh <code>bre/…/attempt-n</code> branch; refuses a dirty tree</td></tr>
    <tr><td><b>Changed files are facts</b></td><td class="muted">recorded from <code>git diff</code>, never from what an agent says</td></tr>
    <tr><td><b>An agent can't cheat the suite</b></td><td class="muted">diff guard rejects deleted / skipped / vacuous tests and CI edits</td></tr>
    <tr><td><b>Failure leaves nothing behind</b></td><td class="muted">exact rollback; never touches your untracked files; the rejected patch is kept as evidence</td></tr>
    <tr><td><b>The loop terminates</b></td><td class="muted">attempt cap → ABANDONED; untested attempts are abandoned, not refuted</td></tr></table></section>

<!-- 6 -->
<section class="slide"><div class="kicker">Verification</div>
  <h2>Every prediction is written down <span class="accent">before</span> anyone knows if it's right</h2>
  <div class="steps">
    <div class="step"><div class="n">1 · MADE</div><p>Diagnosis, risk level, routing decision and fix plan are each recorded as <b class="amber">pending</b>, with their full component breakdown.</p></div>
    <div class="step"><div class="n">2 · TESTED</div><p>Three levels, fail-fast: the failing test → its file → the whole suite. No reproducing test ⇒ <b>no verified fix</b>. Zero tests collected is never a pass.</p></div>
    <div class="step"><div class="n">3 · CLOSED</div><p>Only a real verification run may close it: <b class="green">confirmed</b> or <b class="red">refuted</b>. Never tested? <b class="muted">abandoned</b> — no reputation moves.</p></div></div>
  <p style="margin-top:34px;font-size:28px">The verifier is a <b>deterministic test-suite exit code</b> — not a model grading itself.</p></section>

<!-- 7 -->
<section class="slide"><div class="kicker">Learning</div>
  <h2>It learns <span class="accent">who was right</span> — not who sounded right</h2>
  <div class="row"><div class="col">
    <p>Built on <b>ASMOS</b>: per-topic ownership learned only from verification-backed outcomes.</p>
    <p style="margin-top:14px"><code>Trust = (7 + verified_correct) / (10 + verified_total)</code></p>
    <p style="margin-top:8px"><code>Ownership = 0.6·Trust + 0.4·Share</code></p>
    <p style="margin-top:8px"><code>Route to memory iff Sim × Ownership ≥ τ</code></p>
    <p class="small muted" style="margin-top:14px">Pinned to the real ASMOS source by <b>95 parity tests</b>. τ is tuned from data, on a simulator validated against the measured runs ({{VALIDATION}} orderings agree exactly).</p></div>
  <div class="col"><div class="card"><h3 class="violet">Memory</h3><p class="small muted">a diagnosis a passing test suite already vouched for — <b class="green">free</b></p></div>
    <div class="card" style="margin-top:16px"><h3 class="accent">IBM Bob</h3><p class="small muted">a full investigation — <b class="amber">the fallback, correct by construction</b>. A cold start always lands here.</p></div></div></div></section>

<!-- 8 -->
<section class="slide"><div class="kicker">The moment that matters</div>
  <h2>The look-alike: same symptom, <span class="red">different cause</span></h2>
  <div class="steps">
    <div class="step"><div class="n">1</div><p>Same failing test as a past incident. Memory answers: <b>"lower pool_size in config"</b>.</p></div>
    <div class="step"><div class="n">2</div><p>A human approves. The patch lands on its <b>own branch</b> after a checkpoint.</p></div>
    <div class="step"><div class="n">3</div><p><b class="red">The tests say no.</b> The real cause is a hard-coded cap <i>in code</i>.</p></div>
    <div class="step"><div class="n">4</div><p><b>Rolled back exactly.</b> The diagnosis is recorded <b>refuted</b>; the memory loses standing.</p></div>
    <div class="step"><div class="n">5</div><p>Attempt 2 excludes that memory, runs a full investigation, finds the cap, and is <b class="green">verified</b>.</p></div></div>
  <p style="margin-top:30px;font-size:28px">The agent was wrong. The system found out <b>because the tests said so</b>.</p></section>

<!-- 9 -->
<section class="slide"><div class="kicker">Results — read the caveats</div>
  <h2>Bob alone vs BRE: same incidents, real git and pytest</h2>
  <div class="row">{{CARDS}}</div>
  <p class="small muted" style="margin-top:20px"><b>Nominal</b> token costs while Bob is simulated. Reuse, refutation and resolution counts are measured. Small synthetic corpus; τ tuned in-sample. Full report: <code>docs/RESULTS.md</code></p></section>

<!-- 10 -->
<section class="slide"><div class="kicker">Honest limits</div>
  <h2>What this does <span class="red">not</span> show</h2>
  <ul>
    <li><b>Nothing about IBM Bob's diagnostic quality</b> — the agent in the demo is a labelled stand-in until a live run.</li>
    <li><b>Real token costs</b> — the figures are nominal; run <code>--bob live</code> for measured ones.</li>
    <li><b>That τ generalises</b> — 14 synthetic incidents, tuned in-sample.</li>
    <li><b>That ownership <i>evolution</i> helps at this scale</b> — one refutation moves trust ≈0.03 at ASMOS's prior; the frozen-ownership ablation is flat.</li>
    <li>Similarity <b>cannot</b> separate a look-alike from a true match. That is <i>why</i> verification is the gate.</li></ul></section>

<!-- 11 -->
<section class="slide"><div class="kicker">Why it matters</div>
  <h2>Business value · originality</h2>
  <div class="row"><div class="card"><h3 class="green">Value</h3><ul class="small"><li>Fewer wasted agent attempts and tokens on failures already solved</li><li>An audit trail for every AI-authored change: who approved, what was verified, what was rolled back</li><li>A safe way to let agents act near production — the control is structural, not a request in a prompt</li></ul></div>
  <div class="card"><h3 class="violet">Originality</h3><ul class="small"><li>Verification-gated reputation (ASMOS) applied to reliability engineering</li><li>The verifier is a deterministic exit code, not an LLM grading itself</li><li>"The agent was wrong and the system found out" is the headline feature</li><li>An evaluation that includes the adversarial case — and reports its own mistakes</li></ul></div></div></section>

<!-- 12 -->
<section class="slide"><div class="kicker">Try it</div>
  <h2>Run it in 60 seconds — no Bob, no credentials</h2>
  <div class="card"><p><code>.\scripts\run_demo.ps1</code> &nbsp;→&nbsp; <code>http://127.0.0.1:8000</code></p><p class="small muted" style="margin-top:8px">or <code>python scripts/demo.py --twice</code> in a terminal · 300+ tests on real git repos · <code>/cockpit</code> for one-screen project status</p></div>
  <div class="row" style="margin-top:22px"><div class="card"><h3>Next</h3><ul class="small"><li>Live IBM Bob end to end; measured cost</li><li>A smaller ownership prior — faster adaptation</li><li>Real repositories and CI failure feeds</li></ul></div>
  <div class="card"><h3>Repository</h3><p class="small">github.com/mohith1306/ReliabilityEngineer</p><p class="small muted">MIT · public · every design decision has an ADR and a session-ledger entry</p></div></div>
  <div class="foot"><span>Bob Reliability Engineer</span><span>Don't just generate a fix. Verify it.</span></div></section>

</div><div id="hint">← → or click to navigate · Ctrl+P for PDF</div>
<script>
  const slides = [...document.querySelectorAll('.slide')]; let i = 0;
  const fit = () => { const s = Math.min(innerWidth / 1280, innerHeight / 720); slides.forEach(el => el.style.transform = `scale(${s})`); };
  const show = n => { i = Math.max(0, Math.min(slides.length - 1, n)); slides.forEach((el, k) => el.classList.toggle('on', k === i)); location.hash = i + 1; };
  addEventListener('resize', fit); fit();
  addEventListener('keydown', e => { if (['ArrowRight','PageDown',' '].includes(e.key)) show(i + 1); if (['ArrowLeft','PageUp'].includes(e.key)) show(i - 1); if (e.key === 'Home') show(0); if (e.key === 'End') show(slides.length - 1); });
  addEventListener('click', e => show(e.clientX > innerWidth / 2 ? i + 1 : i - 1));
  show((parseInt(location.hash.slice(1)) || 1) - 1);
</script></body></html>
"""

if __name__ == "__main__":
    raise SystemExit(main())
