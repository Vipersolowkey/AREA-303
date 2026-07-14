"""
Build a self-contained results dashboard (single HTML file) for AREA 303
features #01-#05. Embeds each feature's key figure as a data URI so the page has
no external dependencies.

    python code/build_dashboard.py            # -> dashboard.html at repo root
"""
import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dashboard.html"


def img_uri(rel: str) -> str:
    p = ROOT / rel
    if not p.exists():
        return ""
    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


FEATURES = [
    {
        "num": "01", "title": "Review Sentiment", "tag": "NLP",
        "task": "Classify review sentiment (positive / neutral / negative).",
        "approach": "Few-shot LLM (neutral-calibrated prompt), vs rating-derived labels.",
        "data": "fake_reviews (English, 40.5k) · 1200 balanced eval",
        "metrics": [("Accuracy", "0.591"), ("Macro-F1", "0.596")],
        "fig": "review_sentiment/figures/confusion_matrix.png",
        "io": [("“Absolutely love this dress, fabric is soft and fits perfectly!”", "positive"),
               ("“Package arrived dented and the color is off. Not worth it.”", "negative")],
    },
    {
        "num": "05", "title": "Fake Review Detection", "tag": "NLP",
        "task": "Flag computer-generated / fake reviews.",
        "approach": "Few-shot LLM on review text + metadata (rating, category).",
        "data": "fake_reviews CG/OR (English) · 1000 balanced eval",
        "metrics": [("Accuracy", "0.767"), ("Macro-F1", "0.766")],
        "fig": "fake_review/figures/pr_curve.png",
        "io": [("“Fits true to size, cotton is breathable, held up after washing.”", "genuine 0.85"),
               ("“Amazing! Love it! Best product ever! Highly recommend!”", "fake 0.90")],
    },
    {
        "num": "02", "title": "Dynamic Pricing", "tag": "Pricing",
        "task": "Recommend a competitive selling price.",
        "approach": "Embed comparable products → retrieve top-K → LLM reasons a price.",
        "data": "ASOS clothing (GBP) · comps k=10 · 1500 / 40 eval",
        "metrics": [("LLM MAPE", "12.5%"), ("Baseline MAPE", "25.8%")],
        "fig": "dynamic_pricing/figures/pred_vs_actual.png",
        "io": [("Faux leather biker jacket in black", "£52  (range £42–£70)")],
    },
    {
        "num": "03", "title": "Personal Shopper", "tag": "RAG",
        "task": "Answer shopping queries with grounded top-K picks.",
        "approach": "Embed catalog → retrieve → LLM writes recommendation (RAG).",
        "data": "ASOS + cosmetics (6k products) · known-item recall",
        "metrics": [("Recall@1", "0.887"), ("Recall@5", "0.987")],
        "fig": "personal_shopper/figures/recall_at_k.png",
        "io": [("“warm waterproof jacket for hiking”", "North Face ski jacket +2"),
               ("“long-lasting matte red lipstick”", "Lancôme Matte Wear +2")],
    },
    {
        "num": "04", "title": "Customer Churn", "tag": "Behavioral",
        "task": "Score churn risk + drivers + retention action.",
        "approach": "Distil behaviour → LLM risk score (0–1). Rule baseline for reference.",
        "data": "REES46 events (real, free) · 48k users · 1500 / 200 eval",
        "metrics": [("LLM AUC", "0.775"), ("F1@0.5", "0.718")],
        "fig": "customer_churn/figures/roc_curve.png",
        "io": [("recency 210d · freq 2 · declining", "churn 0.85 → re-engage"),
               ("recency 8d · freq 14 · growing", "churn 0.10 → nurture")],
    },
]

SUMMARY = [
    ("5 / 5", "features live"),
    ("English", "platform"),
    ("gpt-4o-mini", "LLM backend"),
    ("0", "models trained"),
    ("< $1", "eval cost"),
]


def card_html(f: dict) -> str:
    metrics = "".join(
        f'<div class="metric"><span class="mval">{v}</span>'
        f'<span class="mlabel">{k}</span></div>' for k, v in f["metrics"])
    io = "".join(
        f'<div class="io"><span class="in">{i}</span>'
        f'<span class="arrow">→</span><span class="out">{o}</span></div>'
        for i, o in f["io"])
    uri = img_uri(f["fig"])
    fig = (f'<img class="fig" src="{uri}" alt="{f["title"]} chart" loading="lazy">'
           if uri else '<div class="fig fig-missing">figure not built</div>')
    return f"""
    <article class="card">
      <header class="card-h">
        <span class="num">{f['num']}</span>
        <h3>{f['title']}</h3>
        <span class="tag">{f['tag']}</span>
        <span class="live" title="running">LIVE</span>
      </header>
      <p class="task">{f['task']}</p>
      <p class="approach">{f['approach']}</p>
      <div class="metrics">{metrics}</div>
      <figure>{fig}</figure>
      <div class="ios">{io}</div>
      <p class="data">{f['data']}</p>
    </article>"""


def build() -> str:
    cards = "\n".join(card_html(f) for f in FEATURES)
    tiles = "".join(
        f'<div class="tile"><span class="tval">{v}</span>'
        f'<span class="tlabel">{k}</span></div>' for v, k in SUMMARY)
    return f"""<title>AREA 303 — AI Features Results</title>
<style>
:root {{
  --bg: #f4f6f7; --panel: #ffffff; --ink: #17211f; --muted: #5c6a67;
  --line: #dde3e2; --accent: #0f766e; --accent-soft: #d7ebe7;
  --good: #15803d; --warn: #b45309; --chip: #eef2f1;
  --mono: ui-monospace, "Cascadia Code", "SF Mono", Menlo, monospace;
  --sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #0e1413; --panel: #161e1d; --ink: #e8efed; --muted: #93a29f;
    --line: #26302e; --accent: #4fd1c1; --accent-soft: #12312c; --chip: #1c2624;
    --good: #4ade80; --warn: #fbbf24;
  }}
}}
:root[data-theme="dark"] {{
  --bg: #0e1413; --panel: #161e1d; --ink: #e8efed; --muted: #93a29f;
  --line: #26302e; --accent: #4fd1c1; --accent-soft: #12312c; --chip: #1c2624;
  --good: #4ade80; --warn: #fbbf24;
}}
:root[data-theme="light"] {{
  --bg: #f4f6f7; --panel: #ffffff; --ink: #17211f; --muted: #5c6a67;
  --line: #dde3e2; --accent: #0f766e; --accent-soft: #d7ebe7; --chip: #eef2f1;
  --good: #15803d; --warn: #b45309;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--ink); font-family: var(--sans);
  line-height: 1.5; -webkit-font-smoothing: antialiased; }}
.wrap {{ max-width: 1080px; margin: 0 auto; padding: 2.5rem 1.25rem 4rem; }}
.topbar {{ height: 3px; background: linear-gradient(90deg, var(--accent), transparent); }}
header.page {{ margin-bottom: 2rem; }}
.eyebrow {{ font-family: var(--mono); font-size: 12px; letter-spacing: .12em;
  text-transform: uppercase; color: var(--accent); margin: 0 0 .5rem; }}
h1 {{ font-size: clamp(1.6rem, 3.5vw, 2.4rem); margin: 0 0 .4rem; letter-spacing: -.02em;
  text-wrap: balance; }}
.sub {{ color: var(--muted); max-width: 60ch; margin: 0; }}
.tiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 1px; background: var(--line); border: 1px solid var(--line); border-radius: 12px;
  overflow: hidden; margin: 1.75rem 0 2.25rem; }}
.tile {{ background: var(--panel); padding: 1rem 1.1rem; display: flex; flex-direction: column; gap: .15rem; }}
.tval {{ font-family: var(--mono); font-size: 1.15rem; font-weight: 600; color: var(--accent);
  font-variant-numeric: tabular-nums; }}
.tlabel {{ font-size: 12px; color: var(--muted); }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1rem; }}
.card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
  padding: 1.1rem 1.2rem 1.2rem; display: flex; flex-direction: column; gap: .55rem; }}
.card-h {{ display: flex; align-items: center; gap: .55rem; }}
.num {{ font-family: var(--mono); font-size: 12px; color: var(--muted); border: 1px solid var(--line);
  border-radius: 6px; padding: 1px 6px; }}
.card-h h3 {{ font-size: 1.05rem; margin: 0; letter-spacing: -.01em; }}
.tag {{ font-family: var(--mono); font-size: 10.5px; letter-spacing: .06em; text-transform: uppercase;
  background: var(--accent-soft); color: var(--accent); padding: 2px 7px; border-radius: 20px; }}
.live {{ margin-left: auto; font-family: var(--mono); font-size: 10px; letter-spacing: .1em;
  color: var(--good); display: inline-flex; align-items: center; gap: 5px; }}
.live::before {{ content: ""; width: 6px; height: 6px; border-radius: 50%; background: var(--good); }}
.task {{ margin: 0; font-weight: 500; }}
.approach {{ margin: 0; font-size: 13.5px; color: var(--muted); }}
.metrics {{ display: flex; gap: .5rem; margin: .25rem 0; }}
.metric {{ flex: 1; background: var(--chip); border-radius: 8px; padding: .55rem .6rem;
  display: flex; flex-direction: column; gap: 1px; }}
.mval {{ font-family: var(--mono); font-size: 1.25rem; font-weight: 600; font-variant-numeric: tabular-nums; }}
.mlabel {{ font-size: 11px; color: var(--muted); }}
figure {{ margin: 0; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; background: #fff; }}
.fig {{ display: block; width: 100%; height: auto; max-height: 240px; object-fit: contain; }}
.fig-missing {{ padding: 2rem; text-align: center; color: var(--muted); font-family: var(--mono); font-size: 12px; }}
.ios {{ display: flex; flex-direction: column; gap: .35rem; }}
.io {{ display: grid; grid-template-columns: 1fr auto auto; gap: .5rem; align-items: baseline;
  font-size: 12.5px; }}
.io .in {{ color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.io .arrow {{ color: var(--accent); }}
.io .out {{ font-family: var(--mono); font-weight: 600; white-space: nowrap; }}
.data {{ margin: .2rem 0 0; font-family: var(--mono); font-size: 11px; color: var(--muted); }}
footer {{ margin-top: 2.5rem; padding-top: 1.25rem; border-top: 1px solid var(--line);
  color: var(--muted); font-size: 13px; }}
footer b {{ color: var(--ink); font-weight: 600; }}
footer .row {{ margin: .3rem 0; }}
</style>
<div class="topbar"></div>
<div class="wrap">
  <header class="page">
    <p class="eyebrow">AREA 303 · AI/ML Prototype</p>
    <h1>AI features for small &amp; medium fashion + cosmetics sellers</h1>
    <p class="sub">Five LLM-powered features — sentiment, review integrity, pricing, discovery,
      and retention. Built LLM-first with <b>no model training</b>: each feature calls an LLM
      for inference and is evaluated on real labelled data.</p>
  </header>
  <section class="tiles">{tiles}</section>
  <section class="grid">
{cards}
  </section>
  <footer>
    <div class="row"><b>Approach.</b> Backend-agnostic LLM client (OpenAI gpt-4o-mini by default,
      or local Ollama qwen2.5 + bge-m3). Labelled data is used for evaluation, not training.</div>
    <div class="row"><b>Data.</b> English, free sources — fake_reviews (reviews), ASOS (clothing),
      makeup-1000 (cosmetics), REES46 event logs (churn). No paid data required.</div>
    <div class="row"><b>Not in scope.</b> UI/API server · model training · ideas #06–#17.</div>
  </footer>
</div>"""


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    kb = OUT.stat().st_size / 1024
    print(f"Wrote {OUT.relative_to(ROOT)} ({kb:.0f} KB)")
