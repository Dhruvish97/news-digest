#!/usr/bin/env python3
"""
Daily World News Digest
Fetches top 10 global news stories and renders a self-contained HTML newsletter.
No external CDN dependencies — system fonts, CSS gradients, inline SVG charts.
"""

import sys
import json
import math
import webbrowser
from collections import Counter
from datetime import datetime
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "digest.html"

# Category → (accent color, dark gradient start, dark gradient end, emoji)
CATEGORY_META = {
    "Politics":       ("#ef4444", "#450a0a", "#1c0303", "🏛️"),
    "Tech":           ("#6366f1", "#1e1b4b", "#0d0b2a", "💻"),
    "Finance":        ("#f59e0b", "#78350f", "#3f1a00", "📈"),
    "Science":        ("#10b981", "#064e3b", "#022c22", "🔬"),
    "Environment":    ("#22c55e", "#14532d", "#052e16", "🌿"),
    "Health":         ("#ec4899", "#831843", "#4a0a28", "🏥"),
    "War & Conflict": ("#dc2626", "#7f1d1d", "#1c0505", "⚔️"),
    "Business":       ("#8b5cf6", "#4c1d95", "#2d0f5e", "🏢"),
    "Society":        ("#0ea5e9", "#0c4a6e", "#04243d", "🌐"),
    "Other":          ("#94a3b8", "#1e293b", "#0f172a", "📰"),
}

def cat_meta(category: str) -> tuple:
    for key, meta in CATEGORY_META.items():
        if key.lower() in category.lower():
            return meta
    return CATEGORY_META["Other"]

def reading_time(text: str) -> str:
    mins = max(1, round(len(text.split()) / 200))
    return f"{mins} min read"

# ── SVG chart generators (no external libs) ────────────────────────────────────

def svg_bar_chart(stories: list[dict]) -> str:
    W, H = 580, 210
    pl, pr, pt, pb = 28, 16, 20, 28
    bw = (W - pl - pr) / len(stories)
    bar_w = bw * 0.55
    area_h = H - pt - pb

    # gridlines
    grid = ""
    for v in [2, 4, 6, 8, 10]:
        y = pt + area_h - (v / 10) * area_h
        grid += (f'<line x1="{pl}" y1="{y:.1f}" x2="{W-pr}" y2="{y:.1f}" '
                 f'stroke="#1a2942" stroke-width="1"/>'
                 f'<text x="{pl-4}" y="{y+3:.1f}" text-anchor="end" '
                 f'font-size="8" fill="#475569">{v}</text>')

    bars = ""
    for i, s in enumerate(stories):
        x = pl + i * bw + (bw - bar_w) / 2
        bh = max(2, (s["importance_score"] / 10) * area_h)
        y  = pt + area_h - bh
        color = cat_meta(s["category"])[0]
        cx = x + bar_w / 2
        bars += (f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
                 f'rx="3" fill="{color}" opacity="0.88"/>'
                 f'<text x="{cx:.1f}" y="{y-3:.1f}" text-anchor="middle" '
                 f'font-size="9" fill="#94a3b8">{s["importance_score"]}</text>'
                 f'<text x="{cx:.1f}" y="{H-5:.1f}" text-anchor="middle" '
                 f'font-size="9" fill="#64748b">#{s["rank"]}</text>')

    return (f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
            f'style="width:100%;height:auto">{grid}{bars}</svg>')


def svg_donut_chart(cat_counts: dict) -> str:
    cx = cy = 100
    r_out, r_in = 82, 50
    total = sum(cat_counts.values())
    angle = -math.pi / 2
    segments = ""
    legend_items = ""

    for idx, (cat, count) in enumerate(cat_counts.items()):
        sweep = (count / total) * 2 * math.pi
        end   = angle + sweep
        color = cat_meta(cat)[0]
        laf   = 1 if sweep > math.pi else 0

        def pt(a, rad): return (cx + rad * math.cos(a), cy + rad * math.sin(a))

        ox, oy   = pt(angle, r_out)
        ox2, oy2 = pt(end,   r_out)
        ix, iy   = pt(angle, r_in)
        ix2, iy2 = pt(end,   r_in)

        d = (f"M {ox:.2f} {oy:.2f} "
             f"A {r_out} {r_out} 0 {laf} 1 {ox2:.2f} {oy2:.2f} "
             f"L {ix2:.2f} {iy2:.2f} "
             f"A {r_in} {r_in} 0 {laf} 0 {ix:.2f} {iy:.2f} Z")
        segments += f'<path d="{d}" fill="{color}" stroke="#0b1120" stroke-width="2.5"/>'

        ly = 18 + idx * 20
        legend_items += (
            f'<rect x="216" y="{ly-9}" width="9" height="9" rx="2" fill="{color}"/>'
            f'<text x="230" y="{ly}" font-size="10" fill="#94a3b8">{cat}</text>'
            f'<text x="355" y="{ly}" font-size="10" fill="#64748b" '
            f'text-anchor="end">{count}</text>'
        )
        angle = end

    center = (f'<text x="{cx}" y="{cy-4}" text-anchor="middle" font-size="24" '
              f'font-weight="700" fill="#f0f4f8">{total}</text>'
              f'<text x="{cx}" y="{cy+14}" text-anchor="middle" font-size="9" '
              f'fill="#64748b" letter-spacing="1">STORIES</text>')

    return (f'<svg viewBox="0 0 380 200" xmlns="http://www.w3.org/2000/svg" '
            f'style="width:100%;height:auto">{segments}{center}{legend_items}</svg>')


# ── Stories loader ──────────────────────────────────────────────────────────────

def load_stories() -> list[dict]:
    """Load pre-researched stories from --from-file PATH or --from-json '[...]'."""
    args = sys.argv[1:]
    if "--from-file" in args:
        path = args[args.index("--from-file") + 1]
        return json.loads(Path(path).read_text())
    if "--from-json" in args:
        return json.loads(args[args.index("--from-json") + 1])
    raise SystemExit(
        "Usage: digest.py --from-file stories.json\n"
        "       digest.py --from-json '[{...}]'\n\n"
        "Tip: use /daily-news in Claude to research and render automatically."
    )


# ── HTML renderer ───────────────────────────────────────────────────────────────

def render_html(stories: list[dict]) -> str:
    now      = datetime.now()
    date_str = now.strftime("%A, %B %d, %Y")
    time_str = now.strftime("%I:%M %p")
    hero     = stories[0]
    featured = stories[1:3]
    rest     = stories[3:]

    # ── Hero ──────────────────────────────────────────────────────────────────
    h_color, h_g1, h_g2, h_icon = cat_meta(hero["category"])
    hero_html = f"""
    <div class="hero" style="--g1:{h_g1};--g2:{h_g2};--ac:{h_color}">
      <div class="hero-visual">
        <div class="hero-icon" aria-hidden="true">{h_icon}</div>
        <div class="hero-num" aria-hidden="true">01</div>
      </div>
      <div class="hero-body">
        <div class="tag-row">
          <span class="cat-tag" style="--c:{h_color}">{hero['category']}</span>
          <span class="region-pill">📍 {hero['region']}</span>
          <span class="read-time">⏱ {reading_time(hero['summary'])}</span>
          <span class="score-pill">⚡ {hero['importance_score']}/10</span>
        </div>
        <h2 class="hero-headline">{hero['headline']}</h2>
        <p class="hero-summary">{hero['summary']}</p>
        <div class="hero-foot">
          <span class="breaking-badge">🔥 Top Story</span>
          <span class="source-name">📰 {hero['source']}</span>
        </div>
      </div>
    </div>"""

    # ── Featured cards (#2-3) ─────────────────────────────────────────────────
    feat_html = ""
    for s in featured:
        f_color, f_g1, f_g2, f_icon = cat_meta(s["category"])
        trending = '<span class="trend-badge">🔥 Trending</span>' if s["rank"] <= 3 else ""
        feat_html += f"""
        <article class="feat-card" style="--g1:{f_g1};--g2:{f_g2};--ac:{f_color}">
          <div class="feat-visual">
            <div class="feat-icon" aria-hidden="true">{f_icon}</div>
            <span class="rank-pill">#{s['rank']}</span>
            {trending}
          </div>
          <div class="feat-body">
            <div class="tag-row">
              <span class="cat-tag" style="--c:{f_color}">{s['category']}</span>
              <span class="region-pill">📍 {s['region']}</span>
              <span class="read-time">⏱ {reading_time(s['summary'])}</span>
            </div>
            <h3 class="feat-headline">{s['headline']}</h3>
            <p class="feat-summary">{s['summary']}</p>
            <div class="card-foot">
              <span class="source-name">📰 {s['source']}</span>
              <span class="score-pill">⚡ {s['importance_score']}/10</span>
            </div>
          </div>
        </article>"""

    # ── Grid cards (#4-10) ────────────────────────────────────────────────────
    grid_html = ""
    for s in rest:
        g_color, g_g1, g_g2, g_icon = cat_meta(s["category"])
        grid_html += f"""
        <article class="card" style="--ac:{g_color};--g1:{g_g1}">
          <div class="card-accent-bar" style="background:{g_color}"></div>
          <div class="card-body">
            <div class="card-visual-row">
              <span class="card-icon" aria-hidden="true">{g_icon}</span>
              <span class="rank-num">#{s['rank']}</span>
            </div>
            <div class="tag-row">
              <span class="cat-tag" style="--c:{g_color}">{s['category']}</span>
              <span class="read-time">⏱ {reading_time(s['summary'])}</span>
            </div>
            <h4 class="card-headline">{s['headline']}</h4>
            <p class="card-summary">{s['summary']}</p>
            <div class="card-foot">
              <span class="source-name">📰 {s['source']}</span>
              <span class="region-pill sm">📍 {s['region']}</span>
            </div>
          </div>
        </article>"""

    # ── Ticker ────────────────────────────────────────────────────────────────
    ticker_items = " &nbsp;·&nbsp; ".join(
        f"<b>#{s['rank']}</b> {s['headline']}" for s in stories
    )

    # ── SVG charts ────────────────────────────────────────────────────────────
    cat_counts = Counter(s["category"] for s in stories)
    bar_svg    = svg_bar_chart(stories)
    donut_svg  = svg_donut_chart(cat_counts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>World News Digest — {date_str}</title>
<style>
/* ── Design tokens ──────────────────────────────────────────────────────── */
:root {{
  /* Backgrounds */
  --bg:       #080f1e;
  --surface:  #0f1b30;
  --surface2: #162236;
  --surface3: #1c2d45;

  /* Text */
  --text:   #eef2f7;
  --text2:  #b8cce0;
  --muted:  #6b8aab;
  --faint:  #3d5470;

  /* Accents */
  --accent: #38bdf8;
  --gold:   #f59e0b;
  --red:    #ef4444;

  /* Structure */
  --border: #1c3050;
  --r:      10px;
  --r-lg:   16px;

  /* Typography — system fonts only, zero CDN */
  --font-head: 'Georgia', 'Times New Roman', serif;
  --font-body: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue',
               Arial, sans-serif;
  --font-mono: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
}}

/* ── Reset ──────────────────────────────────────────────────────────────── */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: var(--font-body);
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
  line-height: 1.5;
}}

/* ── Ticker ──────────────────────────────────────────────────────────────── */
.ticker-wrap {{
  overflow: hidden;
  background: var(--accent);
  color: #060e1c;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: .3px;
  padding: 6px 0;
  white-space: nowrap;
}}
.ticker-track {{
  display: inline-block;
  animation: ticker 70s linear infinite;
  padding-left: 100%;
}}
.ticker-track:hover {{ animation-play-state: paused; }}
.ticker-live {{
  background: #060e1c;
  color: var(--accent);
  padding: 1px 10px;
  margin-right: 16px;
  border-radius: 2px;
  font-size: 0.6rem;
  letter-spacing: 1.5px;
  text-transform: uppercase;
}}
@keyframes ticker {{ to {{ transform: translateX(-50%); }} }}

/* ── Masthead ─────────────────────────────────────────────────────────────── */
.masthead {{
  background: linear-gradient(180deg, #0b1628 0%, var(--bg) 100%);
  border-bottom: 2px solid var(--accent);
  padding: 20px 44px;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}}
.brand-name {{
  font-family: var(--font-head);
  font-size: clamp(1.7rem, 3.5vw, 2.8rem);
  font-weight: 700;
  letter-spacing: -1.5px;
  line-height: 1;
  color: var(--text);
}}
.brand-name em {{ color: var(--accent); font-style: normal; }}
.brand-sub {{
  color: var(--muted);
  font-size: 0.7rem;
  letter-spacing: 2px;
  text-transform: uppercase;
  margin-top: 6px;
}}
.masthead-date {{
  text-align: right;
}}
.masthead-date .d {{
  font-family: var(--font-head);
  font-size: 1rem;
  color: var(--text2);
}}
.masthead-date .t {{
  font-size: 0.72rem;
  color: var(--muted);
  margin-top: 3px;
  font-family: var(--font-mono);
}}

/* ── Layout ──────────────────────────────────────────────────────────────── */
main {{ max-width: 1300px; margin: 0 auto; padding: 36px 22px 80px; }}

.section-header {{
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 22px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}}
.section-header::before {{
  content: '';
  width: 3px; height: 16px;
  background: var(--accent);
  border-radius: 2px;
  flex-shrink: 0;
}}
.section-header h2 {{
  font-family: var(--font-mono);
  font-size: 0.62rem;
  font-weight: 600;
  letter-spacing: 2.5px;
  text-transform: uppercase;
  color: var(--muted);
}}

/* ── Tag / pill components ────────────────────────────────────────────────── */
.tag-row {{
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}}
.cat-tag {{
  font-family: var(--font-mono);
  font-size: 0.58rem;
  font-weight: 600;
  letter-spacing: 1px;
  text-transform: uppercase;
  padding: 3px 8px;
  border-radius: 3px;
  color: #fff;
  background: var(--c, #6b7280);
}}
.region-pill {{
  font-size: 0.62rem;
  color: var(--muted);
  background: var(--surface3);
  padding: 2px 8px;
  border-radius: 3px;
  border: 1px solid var(--border);
}}
.region-pill.sm {{ font-size: 0.58rem; }}
.read-time  {{ font-size: 0.6rem;  color: var(--muted); }}
.score-pill {{
  font-size: 0.6rem;
  font-weight: 700;
  color: var(--gold);
  margin-left: auto;
}}
.source-name {{ font-size: 0.68rem; color: var(--muted); }}

.rank-pill {{
  position: absolute;
  top: 10px; left: 10px;
  background: rgba(8,15,30,.82);
  color: var(--accent);
  font-family: var(--font-mono);
  font-size: 0.68rem;
  font-weight: 700;
  padding: 3px 9px;
  border-radius: 4px;
  border: 1px solid rgba(56,189,248,.35);
  backdrop-filter: blur(6px);
  z-index: 2;
}}
.trend-badge {{
  position: absolute;
  top: 10px; right: 10px;
  background: rgba(220,38,38,.88);
  color: #fff;
  font-size: 0.58rem;
  font-weight: 700;
  padding: 3px 9px;
  border-radius: 4px;
  z-index: 2;
  animation: blink 2.4s ease-in-out infinite;
}}
@keyframes blink {{ 0%,100% {{ opacity:1 }} 50% {{ opacity:.65 }} }}

/* ── Card footer row ─────────────────────────────────────────────────────── */
.card-foot {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
}}

/* ── Hero ────────────────────────────────────────────────────────────────── */
.hero {{
  display: grid;
  grid-template-columns: 320px 1fr;
  border-radius: var(--r-lg);
  overflow: hidden;
  margin-bottom: 44px;
  border: 1px solid var(--border);
  box-shadow: 0 12px 56px rgba(0,0,0,.55);
  min-height: 380px;
}}
@media (max-width: 860px) {{ .hero {{ grid-template-columns: 1fr; }} }}

.hero-visual {{
  background: linear-gradient(145deg, var(--g1), var(--g2));
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  padding: 32px 20px;
  /* subtle dot grid */
  background-image:
    radial-gradient(circle, rgba(255,255,255,.06) 1px, transparent 1px),
    linear-gradient(145deg, var(--g1), var(--g2));
  background-size: 22px 22px, 100% 100%;
}}
.hero-icon {{
  font-size: 5rem;
  line-height: 1;
  filter: drop-shadow(0 4px 20px rgba(0,0,0,.5));
  margin-bottom: 16px;
}}
.hero-num {{
  font-family: var(--font-head);
  font-size: 6.5rem;
  font-weight: 700;
  color: rgba(255,255,255,.06);
  line-height: 1;
  position: absolute;
  bottom: -10px;
  right: 10px;
  pointer-events: none;
  user-select: none;
}}

.hero-body {{
  background: var(--surface);
  padding: 32px 36px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  position: relative;
  border-left: 3px solid var(--ac, var(--accent));
}}
.hero-headline {{
  font-family: var(--font-head);
  font-size: clamp(1.25rem, 2.2vw, 1.9rem);
  font-weight: 700;
  line-height: 1.25;
  color: var(--text);
  margin-bottom: 14px;
}}
.hero-summary {{
  font-size: 0.875rem;
  line-height: 1.75;
  color: var(--text2);
  flex: 1;
}}
.hero-foot {{
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}}
.breaking-badge {{
  background: var(--red);
  color: #fff;
  font-family: var(--font-mono);
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  padding: 4px 12px;
  border-radius: 4px;
  animation: pulse-glow 2.8s ease-in-out infinite;
}}
@keyframes pulse-glow {{
  0%,100% {{ box-shadow: 0 0 0 0 rgba(239,68,68,.4); }}
  50%      {{ box-shadow: 0 0 0 7px rgba(239,68,68,0); }}
}}

/* ── Featured cards (#2-3) ───────────────────────────────────────────────── */
.featured-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
  margin-bottom: 44px;
}}
@media (max-width: 680px) {{ .featured-grid {{ grid-template-columns: 1fr; }} }}

.feat-card {{
  border-radius: var(--r-lg);
  overflow: hidden;
  border: 1px solid var(--border);
  background: var(--surface);
  box-shadow: 0 4px 24px rgba(0,0,0,.4);
  transition: transform .22s, border-color .22s, box-shadow .22s;
  display: flex;
  flex-direction: column;
}}
.feat-card:hover {{
  transform: translateY(-4px);
  border-color: var(--ac, var(--accent));
  box-shadow: 0 12px 40px rgba(0,0,0,.5);
}}
.feat-visual {{
  background-image:
    radial-gradient(circle, rgba(255,255,255,.05) 1px, transparent 1px),
    linear-gradient(145deg, var(--g1), var(--g2));
  background-size: 20px 20px, 100% 100%;
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  font-size: 3rem;
  flex-shrink: 0;
}}
.feat-body {{
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  flex: 1;
  border-top: 2px solid var(--ac, var(--accent));
}}
.feat-headline {{
  font-family: var(--font-head);
  font-size: 1rem;
  font-weight: 700;
  line-height: 1.35;
  color: var(--text);
  margin-bottom: 9px;
}}
.feat-summary {{
  font-size: 0.78rem;
  line-height: 1.65;
  color: var(--text2);
  flex: 1;
}}

/* ── Grid cards (#4-10) ──────────────────────────────────────────────────── */
.news-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  margin-bottom: 52px;
}}
.card {{
  background: var(--surface);
  border-radius: var(--r);
  overflow: hidden;
  border: 1px solid var(--border);
  box-shadow: 0 3px 16px rgba(0,0,0,.35);
  display: flex;
  transition: transform .2s, border-color .2s, box-shadow .2s;
}}
.card:hover {{
  transform: translateY(-3px);
  border-color: var(--ac, var(--accent));
  box-shadow: 0 8px 28px rgba(0,0,0,.45);
}}
.card-accent-bar {{
  width: 3px;
  flex-shrink: 0;
  border-radius: var(--r) 0 0 var(--r);
}}
.card-body {{
  padding: 15px 16px;
  display: flex;
  flex-direction: column;
  flex: 1;
}}
.card-visual-row {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}}
.card-icon {{
  font-size: 1.6rem;
  line-height: 1;
}}
.rank-num {{
  font-family: var(--font-mono);
  font-size: 0.7rem;
  font-weight: 700;
  color: var(--faint);
  letter-spacing: .5px;
}}
.card-headline {{
  font-family: var(--font-head);
  font-size: 0.9rem;
  font-weight: 700;
  line-height: 1.4;
  color: var(--text);
  margin-bottom: 7px;
}}
.card-summary {{
  font-size: 0.76rem;
  line-height: 1.6;
  color: var(--text2);
  flex: 1;
}}

/* ── Charts ──────────────────────────────────────────────────────────────── */
.charts-grid {{
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: 18px;
  margin-bottom: 52px;
}}
@media (max-width: 740px) {{ .charts-grid {{ grid-template-columns: 1fr; }} }}
.chart-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  padding: 26px;
  box-shadow: 0 4px 24px rgba(0,0,0,.3);
}}
.chart-title {{
  font-family: var(--font-mono);
  font-size: 0.6rem;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 18px;
}}

/* ── Footer ──────────────────────────────────────────────────────────────── */
footer {{
  border-top: 1px solid var(--border);
  padding: 26px 22px;
  text-align: center;
  color: var(--muted);
  font-size: 0.75rem;
  line-height: 1.9;
}}
.footer-brand {{
  font-family: var(--font-head);
  font-size: 1rem;
  color: var(--text2);
  margin-bottom: 4px;
}}
footer a {{ color: var(--accent); text-decoration: none; }}
</style>
</head>
<body>

<!-- Breaking ticker -->
<div class="ticker-wrap" role="marquee" aria-label="Breaking news ticker">
  <div class="ticker-track">
    <span class="ticker-live">live</span>{ticker_items}
    &nbsp;&nbsp;&nbsp;&nbsp;
    <span class="ticker-live">live</span>{ticker_items}
  </div>
</div>

<!-- Masthead -->
<header class="masthead">
  <div>
    <div class="brand-name">🌍 World <em>News Digest</em></div>
    <div class="brand-sub">Top 10 global stories · Powered by Claude AI</div>
  </div>
  <div class="masthead-date">
    <div class="d">{date_str}</div>
    <div class="t">Generated {time_str}</div>
  </div>
</header>

<main>

  <div class="section-header"><h2>Top Story</h2></div>
  {hero_html}

  <div class="section-header"><h2>Featured Stories</h2></div>
  <div class="featured-grid">{feat_html}</div>

  <div class="section-header"><h2>More Top Stories</h2></div>
  <div class="news-grid">{grid_html}</div>

  <div class="section-header"><h2>Today's Insights</h2></div>
  <div class="charts-grid">
    <div class="chart-card">
      <div class="chart-title">Importance Scores by Story</div>
      {bar_svg}
    </div>
    <div class="chart-card">
      <div class="chart-title">Category Distribution</div>
      {donut_svg}
    </div>
  </div>

</main>

<footer>
  <div class="footer-brand">World News Digest</div>
  Generated by <a href="https://claude.ai">Claude</a>
  with live web search &nbsp;·&nbsp; {date_str} &nbsp;·&nbsp; {time_str}<br>
  <em>Fully self-contained — no external dependencies · Refreshes daily at 7:00 AM</em>
</footer>

</body>
</html>"""


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stories = load_stories()
    html    = render_html(stories)

    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"📄 Newsletter saved → {OUTPUT_FILE}")

    if "--no-open" not in sys.argv:
        webbrowser.open(f"file://{OUTPUT_FILE.resolve()}")
        print("🌐 Opening in browser...")


if __name__ == "__main__":
    main()
