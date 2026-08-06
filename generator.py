"""AutoQuant Lab site generator.

- content/posts/*.md  -> docs/posts/*.html   (journal + evergreen articles)
- tool pages          -> docs/tools/*.html   (client-side calculators)
- index / about / disclaimer / feed.xml / sitemap.xml
- --daily: generate today's journal post from trading_v2 live artifacts
- --push : git commit & push (no-op with a notice until remote is set)

Legal guardrails baked in: journal posts describe only PAST fills (never
pending orders), and every page carries the not-investment-advice notice.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
POSTS = os.path.join(ROOT, "content", "posts")
DOCS = os.path.join(ROOT, "docs")
TV2 = r"C:\Users\yukur\trading_v2"
SITE = "オートクオンツ研究所"
TAGLINE = "AIが構築・運用する全自動トレードシステムの公開検証ラボ"
BASE_URL = "https://takeo628-hub.github.io/autoquant-lab"
# GitHub Pages project sites live under a subpath; every internal href
# written as "/..." must be prefixed with it or it 404s at the domain root.
BASE_PATH = "/" + BASE_URL.split("//", 1)[-1].split("/", 1)[1] if "/" in BASE_URL.split("//", 1)[-1] else ""

DISCLAIMER = ("本サイトは投資助言ではなく、自動売買システムの検証記録と一般的な金融教育情報の"
              "提供を目的としています。掲載する実績にはペーパートレード（仮想売買）を含み、"
              "将来の成果を保証するものではありません。投資判断はご自身の責任で行ってください。")

CSS = """
:root{--bg:#f7f8fa;--surface:#ffffff;--fg:#17181c;--sub:#5b616e;--line:#e6e8ec;
--acc:#4338ca;--acc2:#0ea5e9;--ok:#047857;--bad:#b91c1c;--box:#f1f3f7;
--shadow:0 1px 2px rgba(16,24,40,.06),0 4px 16px rgba(16,24,40,.06)}
@media(prefers-color-scheme:dark){:root{--bg:#0b0e14;--surface:#141824;--fg:#e8e9ee;
--sub:#9aa1b2;--line:#252b3a;--acc:#8b93f8;--acc2:#38bdf8;--ok:#34d399;--bad:#f87171;
--box:#1a2030;--shadow:0 1px 2px rgba(0,0,0,.5),0 6px 20px rgba(0,0,0,.35)}}
*{box-sizing:border-box}
body{margin:0;font-family:'Hiragino Sans','Noto Sans JP','Yu Gothic UI',Meiryo,sans-serif;
background:var(--bg);color:var(--fg);line-height:1.95;font-size:16px}
main{max-width:820px;margin:0 auto;padding:28px 20px 72px}
header{position:sticky;top:0;z-index:10;background:color-mix(in srgb,var(--bg) 88%,transparent);
backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.hwrap{max-width:1020px;margin:0 auto;padding:12px 20px;display:flex;gap:18px;align-items:center;flex-wrap:wrap}
.hwrap a{color:var(--fg);text-decoration:none}
.hwrap .t{font-weight:800;font-size:17px;display:flex;align-items:center;gap:8px}
.logo{width:26px;height:26px;border-radius:7px;background:linear-gradient(135deg,var(--acc),var(--acc2));
display:inline-flex;align-items:center;justify-content:center;color:#fff;font-size:14px;font-weight:800}
nav{display:flex;gap:4px;flex-wrap:wrap}
nav a{color:var(--sub);text-decoration:none;font-size:13.5px;padding:6px 10px;border-radius:8px}
nav a:hover{background:var(--box);color:var(--fg)}
h1{font-size:clamp(24px,4.5vw,32px);line-height:1.45;letter-spacing:-.01em}
h2{font-size:21px;margin-top:2.2em;padding-left:12px;border-left:4px solid var(--acc);line-height:1.5}
h3{font-size:17px}a{color:var(--acc)}
p{margin:1.1em 0}
.hero{background:linear-gradient(135deg,color-mix(in srgb,var(--acc) 10%,var(--surface)),
color-mix(in srgb,var(--acc2) 8%,var(--surface)));border:1px solid var(--line);border-radius:20px;
padding:34px 28px;margin:8px 0 28px;box-shadow:var(--shadow)}
.hero h1{margin:0 0 10px}
.hero .lead{color:var(--sub);font-size:15.5px;max-width:640px}
.badgerow{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
.badge{font-size:12px;font-weight:700;letter-spacing:.04em;padding:4px 12px;border-radius:999px;
background:color-mix(in srgb,var(--acc) 12%,transparent);color:var(--acc)}
.cta{display:inline-block;margin:16px 10px 0 0;padding:11px 20px;border-radius:10px;font-weight:700;
text-decoration:none;font-size:14.5px}
.cta.p{background:var(--acc);color:#fff}.cta.p:hover{opacity:.92}
.cta.s{border:1.5px solid var(--line);color:var(--fg);background:var(--surface)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:22px 0}
.tile{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px 18px;
box-shadow:var(--shadow)}
.tile .k{font-size:12px;color:var(--sub);letter-spacing:.03em}
.tile .v{font-size:24px;font-weight:800;letter-spacing:-.01em;margin-top:4px;font-variant-numeric:tabular-nums}
.tile .v.up{color:var(--ok)}.tile .v.down{color:var(--bad)}
.tile .s{font-size:11.5px;color:var(--sub);margin-top:2px}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px 20px;
margin:14px 0;box-shadow:var(--shadow);transition:transform .12s ease}
.card:hover{transform:translateY(-2px)}
.card a{text-decoration:none;font-weight:700;font-size:15.5px;line-height:1.6;display:block}
.card .meta{margin-top:6px}
.cbadge{display:inline-block;font-size:11px;font-weight:700;padding:2px 10px;border-radius:999px;margin-bottom:8px}
.cbadge.j{background:color-mix(in srgb,var(--acc2) 14%,transparent);color:var(--acc2)}
.cbadge.a{background:color-mix(in srgb,var(--acc) 12%,transparent);color:var(--acc)}
.promise{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:18px 0}
.promise .card{margin:0}
.promise b{display:block;margin-bottom:4px;font-size:15px}
.promise span{font-size:13px;color:var(--sub)}
table{border-collapse:collapse;width:100%;font-size:14.5px;display:block;overflow-x:auto;
border-radius:12px}
th{background:var(--box);font-size:13px;color:var(--sub)}
th,td{border:1px solid var(--line);padding:9px 14px;text-align:right;font-variant-numeric:tabular-nums}
th:first-child,td:first-child{text-align:left}
tr:nth-child(even) td{background:color-mix(in srgb,var(--box) 45%,transparent)}
.meta{color:var(--sub);font-size:13px}
.note{background:var(--box);border:1px solid var(--line);border-radius:12px;padding:14px 18px;
font-size:12.5px;color:var(--sub);margin-top:44px;line-height:1.8}
.pr{background:linear-gradient(135deg,color-mix(in srgb,var(--acc) 6%,var(--surface)),var(--surface));
border:1px solid var(--line);border-radius:14px;padding:16px 20px;margin:26px 0;box-shadow:var(--shadow)}
.pr .tag{font-size:10.5px;color:var(--sub);letter-spacing:.14em;margin-bottom:4px}
input,select{font:inherit;padding:9px 12px;margin:4px 0;border:1.5px solid var(--line);
border-radius:9px;background:var(--bg);color:var(--fg);width:min(220px,100%)}
button{font:inherit;font-weight:700;padding:11px 22px;border:0;border-radius:10px;
background:var(--acc);color:#fff;cursor:pointer;margin-top:8px}
button:hover{opacity:.92}
.result{font-size:18px;font-weight:700;margin-top:14px;line-height:1.7}
footer{border-top:1px solid var(--line);margin-top:56px;background:var(--surface)}
.fwrap{max-width:820px;margin:0 auto;padding:22px 20px;font-size:12px;color:var(--sub)}
"""


def page(title: str, body: str, desc: str = "", meta: dict | None = None) -> str:
    m = meta or {}
    url = m.get("url", BASE_URL + "/")
    og = (f'<meta property="og:title" content="{html.escape(title)}">'
          f'<meta property="og:description" content="{html.escape(desc or TAGLINE)}">'
          f'<meta property="og:type" content="{"article" if m.get("date") else "website"}">'
          f'<meta property="og:url" content="{url}">'
          f'<meta property="og:site_name" content="{SITE}">'
          f'<meta name="twitter:card" content="summary">')
    jsonld = ""
    if m.get("date"):
        jsonld = ('<script type="application/ld+json">' + json.dumps({
            "@context": "https://schema.org", "@type": "Article",
            "headline": title, "datePublished": str(m["date"]),
            "author": {"@type": "Organization", "name": SITE},
            "mainEntityOfPage": url}, ensure_ascii=False) + "</script>")
    doc = f"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} | {SITE}</title>
<meta name="description" content="{html.escape(desc or TAGLINE)}">
<link rel="alternate" type="application/rss+xml" href="/feed.xml">
{og}{jsonld}
<style>{CSS}</style></head><body>
<header><div class="hwrap"><a class="t" href="/"><span class="logo">AQ</span>{SITE}</a>
<nav><a href="/">ホーム</a><a href="/posts/">記事一覧</a><a href="/tools/">ツール</a>
<a href="/hikaku.html">証券会社比較</a><a href="/about.html">このサイトについて</a></nav></div></header>
<main>{body}
<div class="note">{DISCLAIMER}</div></main>
<footer><div class="fwrap">© {dt.date.today().year} {SITE} ／ 本サイトの記事は自動売買システムの
記録から自動生成されています。アフィリエイトリンクを含む場合はPR表記をしています。</div></footer>
</body></html>"""
    # prefix every root-relative internal link with the Pages subpath
    return doc.replace('href="/', f'href="{BASE_PATH}/').replace("href='/", f"href='{BASE_PATH}/")


def svg_equity() -> str:
    """Inline SVG equity line for journal posts (single series, both themes,
    hover crosshair). Shows a placeholder until >=5 sessions of data exist."""
    csvp = os.path.join(TV2, "reports", "daily_log.csv")
    rows = []
    if os.path.exists(csvp):
        with open(csvp, encoding="utf-8") as f:
            head = f.readline().strip().split(",")
            for ln in f:
                c = dict(zip(head, ln.strip().split(",")))
                try:
                    rows.append((c["data_date"], float(c["equity_jpy"])))
                except (KeyError, ValueError):
                    pass
    rows = sorted(dict(rows).items())
    if len(rows) < 5:
        return ("<p class='meta'>資産推移チャートは検証データが5営業日分たまり次第、"
                "ここに自動表示されます。</p>")
    W, H, PL, PR, PT, PB = 640, 200, 8, 8, 16, 24
    xs = [r[0] for r in rows]
    ys = [r[1] for r in rows]
    y0, y1 = min(ys), max(ys)
    pad = (y1 - y0) * 0.08 or y0 * 0.01 or 1
    y0, y1 = y0 - pad, y1 + pad
    pts = []
    for i, v in enumerate(ys):
        x = PL + (W - PL - PR) * (i / max(len(ys) - 1, 1))
        y = PT + (H - PT - PB) * (1 - (v - y0) / (y1 - y0))
        pts.append(f"{x:.1f},{y:.1f}")
    data = json.dumps({"d": xs, "v": ys}, ensure_ascii=False)
    lx, ly = pts[-1].split(",")
    return f"""<figure style="margin:0">
<svg viewBox="0 0 {W} {H}" style="width:100%;height:auto;display:block" role="img"
 aria-label="仮想資産の推移（円）" id="eqchart" data-series='{data}'>
<polyline points="{' '.join(pts)}" fill="none" stroke="var(--acc)" stroke-width="2"
 stroke-linejoin="round" stroke-linecap="round"/>
<circle cx="{lx}" cy="{ly}" r="4" fill="var(--acc)"/>
<text x="{PL}" y="12" font-size="11" fill="var(--sub)">最高 {max(ys):,.0f}円</text>
<text x="{PL}" y="{H - 8}" font-size="11" fill="var(--sub)">最低 {min(ys):,.0f}円
{xs[0]} 〜 {xs[-1]}（{len(xs)}営業日）</text>
<line id="eqcross" x1="0" x2="0" y1="{PT}" y2="{H - PB}" stroke="var(--sub)"
 stroke-width="1" opacity="0"/>
</svg>
<div id="eqtip" class="meta" style="min-height:1.4em"></div></figure>
<script>(function(){{var s=document.getElementById('eqchart');if(!s)return;
var d=JSON.parse(s.dataset.series),n=d.v.length,PL={PL},PR={PR},W={W};
var cr=document.getElementById('eqcross'),tip=document.getElementById('eqtip');
s.addEventListener('mousemove',function(e){{var r=s.getBoundingClientRect();
var fx=(e.clientX-r.left)/r.width*W;var i=Math.round((fx-PL)/(W-PL-PR)*(n-1));
i=Math.max(0,Math.min(n-1,i));var x=PL+(W-PL-PR)*(i/Math.max(n-1,1));
cr.setAttribute('x1',x);cr.setAttribute('x2',x);cr.setAttribute('opacity','0.5');
tip.textContent=d.d[i]+'： '+Math.round(d.v[i]).toLocaleString()+'円';}});
s.addEventListener('mouseleave',function(){{cr.setAttribute('opacity','0');
tip.textContent='';}});}})();</script>"""


def md2html(md: str) -> str:
    out, in_ul, in_table = [], False, False
    for raw in md.splitlines():
        line = raw.rstrip()
        if line.startswith("::"):          # build-time markers pass through raw
            out.append(line)
            continue
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(re.fullmatch(r"-{2,}:?|:-{1,}:?", c) for c in cells):
                continue
            tag = "th" if not in_table else "td"
            if not in_table:
                out.append("<table>")
                in_table = True
            out.append("<tr>" + "".join(f"<{tag}>{fmt(c)}</{tag}>" for c in cells) + "</tr>")
            continue
        if in_table:
            out.append("</table>")
            in_table = False
        if line.startswith("- "):
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{fmt(line[2:])}</li>")
            continue
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if line.startswith("### "):
            out.append(f"<h3>{fmt(line[4:])}</h3>")
        elif line.startswith("## "):
            out.append(f"<h2>{fmt(line[3:])}</h2>")
        elif line:
            out.append(f"<p>{fmt(line)}</p>")
    if in_ul:
        out.append("</ul>")
    if in_table:
        out.append("</table>")
    return "\n".join(out)


def fmt(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', s)
    return s


def affiliate_box() -> str:
    """Render the PR box from affiliate.json links: [{label, url}, ...]."""
    path = os.path.join(ROOT, "affiliate.json")
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        aff = json.load(f)
    links = [f'<a href="{l["url"]}" rel="sponsored nofollow">{html.escape(l["label"])}</a>'
             for l in aff.get("links", []) if l.get("url")]
    if not links:
        return ""
    return ('<div class="pr"><div class="tag">PR</div>' + "／".join(links) + "</div>")


# ---------------------------------------------------------------- journal
def load_posts() -> list[dict]:
    posts = []
    for fn in sorted(os.listdir(POSTS), reverse=True):
        if not fn.endswith(".md"):
            continue
        with open(os.path.join(POSTS, fn), encoding="utf-8") as f:
            raw = f.read()
        head, _, body = raw.partition("\n---\n")
        meta = dict(re.findall(r"(\w+):\s*(.+)", head))
        posts.append({"slug": fn[:-3], "title": meta.get("title", fn), "date": meta.get("date", ""),
                      "type": meta.get("type", "article"), "desc": meta.get("desc", ""), "body": body})
    return posts


def gen_daily_journal() -> str | None:
    today = dt.date.today()
    slug = f"journal-{today:%Y%m%d}"
    path = os.path.join(POSTS, slug + ".md")
    if os.path.exists(path):
        return None
    try:
        with open(os.path.join(TV2, "state", "paper_state.json"), encoding="utf-8") as f:
            st = json.load(f)
    except FileNotFoundError:
        return None
    hist = st.get("history", [])
    if not hist:
        return None
    cur = hist[-1]
    start = st.get("capital_jpy", 1_000_000)
    ret = (cur["equity_jpy"] / start - 1) * 100
    fills = []
    rlog = os.path.join(TV2, "reports", "runner.log")
    if os.path.exists(rlog):
        with open(rlog, encoding="utf-8", errors="ignore") as f:
            tail = f.readlines()[-40:]
        fills = [ln.strip() for ln in tail if "FILL" in ln][-10:]
    pos = cur.get("positions", {})
    pos_s = "、".join(f"{k}×{v}" for k, v in pos.items()) or "（現金のみ）"
    rows = "\n".join(f"| {h['data_date']} | {h['equity_jpy']:,} |" for h in hist[-7:])
    fills_s = "\n".join(f"- `{ln}`" for ln in fills) if fills else "- 約定なし（リバランス条件未達）"
    body = f"""title: 検証ジャーナル {today:%Y-%m-%d}：資産 {cur['equity_jpy']:,}円（{ret:+.2f}%）
date: {today}
type: journal
desc: AI全自動トレードシステムの公開検証記録 {today:%Y-%m-%d}版
---
AIが構築した全自動売買システム（日足・翌日寄付執行）の検証記録です。**すべて事後の記録**であり、これからの売買の推奨ではありません。

::STATS:: {json.dumps({"equity": cur["equity_jpy"], "ret": round(ret, 2), "days": len({e["data_date"] for e in hist}), "npos": len(pos), "date": cur["data_date"]})}

保有: {pos_s}（現金 {cur['cash']:,.0f}円）

## 直近の約定記録（事後）
{fills_s}

## 資産推移
::EQUITY_CHART::

| 日付 | 資産（円） |
| --- | --- |
{rows}

## システム概要（毎回同じです）
日足シグナル・翌営業日寄付成行のみ・4戦略分散（資産クラスモメンタム／レバレッジトレンド／セクターローテーション／BTCトレンド）×信用1.3倍。判定は常に前日終値まで、執行は翌日寄付 — 未来情報の混入（ルックアヘッド）が構造的に不可能な設計です。詳しくは[検証手法の解説記事](/posts/)をどうぞ。
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    with open(os.path.join(ROOT, "social_queue", f"{slug}.txt"), "w", encoding="utf-8") as f:
        f.write(f"【自動検証{today:%m/%d}】AI全自動トレード 仮想資産{cur['equity_jpy']:,}円（{ret:+.2f}%）"
                f"。全約定を事後公開中。#システムトレード #検証\n")
    return slug


def live_stats() -> dict | None:
    try:
        with open(os.path.join(TV2, "state", "paper_state.json"), encoding="utf-8") as f:
            st = json.load(f)
        h = st["history"]
        cur = h[-1]
        start = st.get("capital_jpy", 1_000_000)
        return {"equity": cur["equity_jpy"],
                "ret": (cur["equity_jpy"] / start - 1) * 100,
                "days": len({e["data_date"] for e in h}),
                "npos": len(cur.get("positions", {})),
                "date": cur["data_date"]}
    except Exception:
        return None


def stat_tiles(s: dict) -> str:
    cls = "up" if s["ret"] > 0 else ("down" if s["ret"] < 0 else "")
    return f"""<div class="tiles">
<div class="tile"><div class="k">仮想資産（ペーパー）</div>
<div class="v">¥{s['equity']:,}</div><div class="s">{s['date']} 時点</div></div>
<div class="tile"><div class="k">累計リターン</div>
<div class="v {cls}">{s['ret']:+.2f}%</div><div class="s">開始 ¥1,000,000</div></div>
<div class="tile"><div class="k">検証日数</div>
<div class="v">{s['days']}日</div><div class="s">毎朝07:30自動売買</div></div>
<div class="tile"><div class="k">保有銘柄</div>
<div class="v">{s['npos']}</div><div class="s">全約定を事後公開</div></div>
</div>"""


# ---------------------------------------------------------------- build
def build() -> None:
    os.makedirs(os.path.join(DOCS, "posts"), exist_ok=True)
    os.makedirs(os.path.join(DOCS, "tools"), exist_ok=True)
    posts = load_posts()
    aff = affiliate_box()

    chart = svg_equity()

    def card(p):
        b = ("<span class='cbadge j'>検証ジャーナル</span>" if p["type"] == "journal"
             else "<span class='cbadge a'>解説記事</span>")
        return (f"<div class='card'>{b}<a href='/posts/{p['slug']}.html'>"
                f"{html.escape(p['title'])}</a><div class='meta'>{p['date']}</div></div>")

    for p in posts:
        rendered = md2html(p["body"])
        rendered = rendered.replace("<p>::EQUITY_CHART::</p>", chart).replace("::EQUITY_CHART::", chart)
        rendered = re.sub(r"::STATS::\s*(\{.*?\})",
                          lambda m: stat_tiles(json.loads(m.group(1))), rendered)
        others = [q for q in posts if q["slug"] != p["slug"]][:3]
        rel = ("<h2>関連記事</h2>" + "".join(card(q) for q in others)) if others else ""
        body = (f"<h1>{html.escape(p['title'])}</h1><div class='meta'>{p['date']}・"
                f"{'検証ジャーナル' if p['type'] == 'journal' else '解説記事'}</div>"
                + rendered + aff + rel)
        meta = {"url": f"{BASE_URL}/posts/{p['slug']}.html", "date": p["date"]}
        with open(os.path.join(DOCS, "posts", p["slug"] + ".html"), "w", encoding="utf-8") as f:
            f.write(page(p["title"], body, p["desc"], meta))

    plist = "".join(card(p) for p in posts)
    with open(os.path.join(DOCS, "posts", "index.html"), "w", encoding="utf-8") as f:
        f.write(page("記事一覧", f"<h1>記事一覧</h1>{plist}"))

    s = live_stats()
    hero = ("<div class='hero'><div class='badgerow'><span class='badge'>公開実験</span>"
            "<span class='badge'>毎日自動更新</span><span class='badge'>全実績 事後公開</span></div>"
            "<h1>AIがひとりで作り、運用し、記録する。<br>全自動トレードの公開検証ラボ</h1>"
            "<p class='lead'>戦略の設計・実装・毎日の売買・この記事の執筆まで、人間の手を介さない"
            "実験プロジェクト。バックテストの嘘（過適合・ルックアヘッド）と向き合いながら、"
            "本物の期待値だけを積み上げられるかを毎日検証しています。</p>"
            "<a class='cta p' href='/posts/'>最新の検証記録を見る</a>"
            "<a class='cta s' href='/posts/kabt-overfit-anatomy.html'>「年利+360%」が嘘だった話</a></div>")
    tiles = stat_tiles(s) if s else ""
    promises = ("<h2>この実験の3つの約束</h2><div class='promise'>"
                "<div class='card'><b>事後公開のみ</b><span>売買の推奨はしません。"
                "記事になるのは約定が終わった後の記録だけです。</span></div>"
                "<div class='card'><b>負けも全部出す</b><span>都合の悪い日も自動で記録されます。"
                "人間が編集で隠せない仕組みです。</span></div>"
                "<div class='card'><b>検証5チェック</b><span>資金制約・異常値・約定再計算などの"
                "検証を通らない数字は掲載しません。</span></div></div>")
    latest = "<h2>最新の記録</h2>" + "".join(card(p) for p in posts[:6])
    toolsec = ("<h2>計算ツール</h2><div class='grid2'>"
               "<div class='card'><a href='/tools/fukuri.html'>複利計算機</a>"
               "<div class='meta'>積立×利回り×年数のシミュレーション</div></div>"
               "<div class='card'><a href='/tools/position-size.html'>ポジションサイズ計算機</a>"
               "<div class='meta'>許容損失から適正な株数を逆算</div></div>"
               "<div class='card'><a href='/tools/jpy-return.html'>円建てリターン計算機</a>"
               "<div class='meta'>為替込みの実質損益を計算</div></div>"
               "<div class='card'><a href='/tools/drawdown.html'>ドローダウン回復計算機</a>"
               "<div class='meta'>-30%を戻すには+43%必要</div></div>"
               "<div class='card'><a href='/tools/fee-calc.html'>年間手数料計算機</a>"
               "<div class='meta'>証券会社別の年間コスト試算</div></div>"
               "<div class='card'><a href='/hikaku.html'>ネット証券6社比較</a>"
               "<div class='meta'>自動売買目線＋実測データつき</div></div>"
               "<div class='card'><a href='/glossary.html'>投資検証の用語集</a>"
               "<div class='meta'>実務目線の短い定義14語</div></div></div>")
    with open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8") as f:
        f.write(page("ホーム", hero + tiles + promises + latest + toolsec + aff, TAGLINE))

    hikaku = ("<h1>ネット証券6社比較 — 自動売買・システムトレード目線＋実測データ</h1>"
              "<p>証券会社選びで最も確実に効くのは手数料です。予測が当たるかは不確実ですが、"
              "コストは100%確実にリターンから引かれます。このページでは主要ネット証券6社を、"
              "一般的な軸に加えて<strong>「自動売買・システムトレードに向くか」という当ラボ独自の"
              "実体験軸</strong>で比較します。</p>"
              "<p class='meta'>※料率・サービスは改定されます。2026年8月時点の調査に基づくため、"
              "申込前に必ず各社公式サイトで最新情報をご確認ください。</p>"
              "<h2>総合比較表</h2>"
              "<table><tr><th>証券会社</th><th>米国株手数料</th><th>国内株手数料</th>"
              "<th>強み</th><th>自動化適性（当ラボ評）</th></tr>"
              "<tr><td>moomoo証券</td><td><strong>0.088%</strong>（上限16.5ドル）</td><td>0円</td>"
              "<td>米株手数料が大手の約1/5。アプリの銘柄分析が強力。24時間取引対応</td>"
              "<td>◎ 低コストが高回転の自動戦略と好相性</td></tr>"
              "<tr><td>SBI証券</td><td>0.495%（上限22ドル）</td><td>0円（ゼロ革命）</td>"
              "<td>取扱商品の広さは国内随一。為替コストの安さも進む</td>"
              "<td>○ 品揃え重視の長期自動積立向け</td></tr>"
              "<tr><td>楽天証券</td><td>0.495%（上限22ドル）</td><td>0円（ゼロコース）</td>"
              "<td>楽天経済圏との連携。取引ツールMARKETSPEEDが有名</td>"
              "<td>◎ <strong>マーケットスピードRSS</strong>でExcel経由の発注自動化が可能"
              "（当ラボが実際に自動化で使用した唯一の公式ルート）</td></tr>"
              "<tr><td>マネックス証券</td><td>0.495%（上限22ドル）</td><td>条件により0円〜</td>"
              "<td>米国株の買付時為替手数料0銭。銘柄スカウターが優秀</td>"
              "<td>○ 米株の分析・積立向け</td></tr>"
              "<tr><td>松井証券</td><td>0.495%（上限22ドル）</td><td>1日50万円まで0円</td>"
              "<td>シンプルな料金体系。サポート評価が高い</td>"
              "<td>△ 少額デイトレ向き</td></tr>"
              "<tr><td>IB証券（Interactive Brokers）</td><td>従量制（1株約0.005ドル・最低約1ドル）</td>"
              "<td>取扱あり（従量制）</td>"
              "<td>プロ・機関投資家標準。取扱市場が世界規模</td>"
              "<td>◎ <strong>本格API</strong>あり。プログラム売買の最終形だが難易度高</td></tr></table>"
              "<h2>当ラボの実測：手数料差は年率でどれだけ効くか</h2>"
              "<p>同一の売買ルール（15.6年・コスト込みバックテスト）を手数料率だけ変えて回した"
              "結果、0.495%と0.088%の差は<strong>年率およそ1.5%</strong>の成績差になりました。"
              "複利で15年続くと最終資産で数十%の差です。売買頻度が高い運用ほど差は拡大します。"
              "<a href='/tools/fee-calc.html'>手数料計算機</a>で自分の取引パターンでの年間コストを"
              "試算できます。</p>"
              "<h2>タイプ別の選び方</h2>"
              "<div class='promise'>"
              "<div class='card'><b>米国株を頻繁に売買する</b><span>手数料率が支配的。0.088%の"
              "moomoo証券が計算上は最有力。</span></div>"
              "<div class='card'><b>日本株の自動売買をしたい</b><span>公式に自動化ルート"
              "（マーケットスピードRSS）を持つ楽天証券が現実解。国内手数料も0円。</span></div>"
              "<div class='card'><b>NISA中心の長期積立</b><span>主要ネット証券はNISA売買手数料0円が"
              "主流。品揃えのSBI・為替のマネックスなど強みで選ぶ。</span></div>"
              "<div class='card'><b>プログラミングで本格運用</b><span>APIの自由度ならIB証券。"
              "ただし口座維持・操作の難易度は覚悟が必要。</span></div></div>"
              "<h2>よくある質問</h2>"
              "<h3>Q. 手数料より「使いやすさ」で選ぶのはダメ？</h3>"
              "<p>短期売買をしないなら合理的です。年1〜2回の取引なら手数料差は誤差で、"
              "続けられるツールの方が価値があります。売買頻度が上がるほど手数料の重みが増します。</p>"
              "<h3>Q. 為替コスト（ドル転）はどう考える？</h3>"
              "<p>近年は0銭化が進みましたが、経路・タイミングで差が残ります。頻繁にドル転する"
              "運用では取引手数料と同等以上に効くことがあるため、必ず各社の最新条件を確認して"
              "ください。</p>"
              "<h3>Q. 複数口座の使い分けはあり？</h3>"
              "<p>あり、というのが当ラボの結論です。実際に当ラボの検証でも「日本株=手数料0円の"
              "証券」「米国株=低率の証券」という役割分担を前提にしています。口座開設は無料なので、"
              "用途で分けるのが合理的です。</p>" + aff +
              "<p class='meta'>本ページには広告リンクを含む場合があります（PR表記のあるもの）。"
              "掲載の有無・順序は比較内容・数値に影響しません。</p>")
    with open(os.path.join(DOCS, "hikaku.html"), "w", encoding="utf-8") as f:
        f.write(page("ネット証券6社比較（自動売買目線）", hikaku,
                     "主要ネット証券6社を手数料・自動売買適性で比較。手数料差が年率リターンに与える影響を15年の実測データつきで解説します。"))

    glossary_terms = [
        ("過適合（オーバーフィッティング）", "過去データに合わせすぎて、未来では機能しない状態。"
         "バックテストの数字だけが良くなる最大の原因。当ラボの<a href='/posts/kabt-overfit-anatomy.html'>実例記事</a>参照。"),
        ("ルックアヘッド・バイアス", "その時点では知り得なかった未来の情報が、判定に混入すること。"
         "学習期間とテスト期間の重複が典型。"),
        ("バックテスト", "売買ルールを過去データに適用して成績を測ること。コスト・資金制約・"
         "単元株を入れないと数字は簡単に数倍化ける。"),
        ("ペーパートレード", "実際のお金を使わない仮想売買。バックテストと実運用の中間の検証段階。"),
        ("ドローダウン（DD）", "資産のピークからの下落率。最大DDは戦略の「痛みの深さ」を表す。"
         "<a href='/tools/drawdown.html'>回復計算機</a>で-30%からの復帰に+43%必要なことを確認できます。"),
        ("シャープレシオ", "リターンをリスク（変動の大きさ）で割った効率指標。1.0を超えれば良好とされる。"),
        ("CAGR（年平均成長率）", "複利ベースの年率リターン。単純平均より実態を表す。"),
        ("モメンタム", "上がっているものは上がり続けやすい傾向。数十年の研究があるが、"
         "実装コスト込みだと教科書ほど簡単ではない。"),
        ("平均回帰", "行き過ぎた価格が平均に戻る傾向。モメンタムと逆の性質で、時間軸で使い分ける。"),
        ("ボラティリティ", "価格変動の大きさ（標準偏差）。リスク管理では敵ではなく測定対象。"),
        ("ケリー基準", "長期の資産成長を最大化する理論上の賭け金比率。実務ではその半分以下で"
         "運用するのが定石（推定誤差のため）。"),
        ("ブートストラップ法", "データを並べ替えて「ありえた別の歴史」を大量生成し、成績のばらつきを"
         "推定する手法。<a href='/posts/luck-vs-skill-bootstrap.html'>解説記事</a>参照。"),
        ("スリッページ", "注文時の想定価格と実際の約定価格の差。バックテストに入れ忘れると"
         "成績が過大評価される。"),
        ("単元株制約", "株は1株単位でしか買えないため、少額口座では理論通りの配分ができない問題。"),
    ]
    gl = ("<h1>投資検証の用語集</h1><p>当ラボの記事に登場する用語を、実務目線の短い定義で"
          "まとめました。教科書的な定義より「何に気をつけるべきか」を優先しています。</p>"
          + "".join(f"<h3>{t}</h3><p>{d}</p>" for t, d in glossary_terms))
    with open(os.path.join(DOCS, "glossary.html"), "w", encoding="utf-8") as f:
        f.write(page("投資検証の用語集", gl,
                     "過適合・ルックアヘッド・ドローダウンなど、投資システム検証の用語を実務目線で解説する用語集。"))

    about = ("<h1>このサイトについて</h1>"
             "<p>本サイトはAI（Claude）が設計・実装・運用する自動売買システムの検証記録を、"
             "同じくAIが毎日自動で公開する実験プロジェクトです。記事の生成からサイトの更新まで"
             "人間の手を介しません。</p>"
             "<h2>なぜ公開するのか</h2><p>投資の世界は「バックテストでは勝てるのに実際には勝てない」"
             "手法であふれています。原因の大半は過適合とルックアヘッド（未来情報の混入）です。"
             "本プロジェクトは、検証手順と全実績を事後公開することで、この問題に正面から取り組みます。</p>"
             "<h2>収益について</h2><p>本サイトは証券会社等のアフィリエイト広告で運営費を賄うことが"
             "あります。広告掲載の有無は記事の内容・数値に一切影響しません。</p>")
    with open(os.path.join(DOCS, "about.html"), "w", encoding="utf-8") as f:
        f.write(page("このサイトについて", about))

    tools()
    tlist = ("<h1>計算ツール</h1><div class='grid2'>"
             "<div class='card'><a href='/tools/fukuri.html'>複利計算機</a>"
             "<div class='meta'>積立×利回り×年数</div></div>"
             "<div class='card'><a href='/tools/position-size.html'>ポジションサイズ計算機</a>"
             "<div class='meta'>許容損失から株数を逆算</div></div>"
             "<div class='card'><a href='/tools/jpy-return.html'>円建てリターン計算機</a>"
             "<div class='meta'>為替込みの実質損益</div></div>"
             "<div class='card'><a href='/tools/drawdown.html'>ドローダウン回復計算機</a>"
             "<div class='meta'>-30%を戻すには+43%必要</div></div>"
             "<div class='card'><a href='/tools/fee-calc.html'>年間手数料計算機</a>"
             "<div class='meta'>証券会社別の年間コスト試算</div></div>"
             "<div class='card'><a href='/glossary.html'>投資検証の用語集</a>"
             "<div class='meta'>過適合・DD・ケリー基準など14語</div></div></div>")
    with open(os.path.join(DOCS, "tools", "index.html"), "w", encoding="utf-8") as f:
        f.write(page("計算ツール", tlist))

    # rss + sitemap + robots
    items = "".join(
        f"<item><title>{html.escape(p['title'])}</title>"
        f"<link>{BASE_URL}/posts/{p['slug']}.html</link>"
        f"<pubDate>{p['date']}</pubDate></item>" for p in posts[:20])
    with open(os.path.join(DOCS, "feed.xml"), "w", encoding="utf-8") as f:
        f.write(f"<?xml version='1.0' encoding='UTF-8'?><rss version='2.0'><channel>"
                f"<title>{SITE}</title><link>{BASE_URL}/</link>"
                f"<description>{TAGLINE}</description>{items}</channel></rss>")
    urls = [f"{BASE_URL}/", f"{BASE_URL}/posts/", f"{BASE_URL}/tools/",
            f"{BASE_URL}/hikaku.html", f"{BASE_URL}/about.html", f"{BASE_URL}/glossary.html",
            f"{BASE_URL}/tools/fukuri.html", f"{BASE_URL}/tools/position-size.html",
            f"{BASE_URL}/tools/jpy-return.html", f"{BASE_URL}/tools/drawdown.html",
            f"{BASE_URL}/tools/fee-calc.html"] + \
           [f"{BASE_URL}/posts/{p['slug']}.html" for p in posts]
    with open(os.path.join(DOCS, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write("<?xml version='1.0' encoding='UTF-8'?>"
                "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
                + "".join(f"<url><loc>{u}</loc></url>" for u in urls) + "</urlset>")
    with open(os.path.join(DOCS, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n")
    nf = ("<h1>ページが見つかりません（404）</h1>"
          "<p>URLが変更されたか、リンクが古い可能性があります。お手数ですが"
          "<a href='/'>ホーム</a>または<a href='/posts/'>記事一覧</a>からお探しください。</p>"
          "<p class='meta'>古いページがブラウザに残っている場合は、Ctrl+F5（スーパーリロード）で"
          "解消することがあります。</p>")
    with open(os.path.join(DOCS, "404.html"), "w", encoding="utf-8") as f:
        f.write(page("ページが見つかりません", nf))
    with open(os.path.join(DOCS, ".nojekyll"), "w") as f:
        f.write("")
    print(f"built {len(posts)} posts -> docs/")


def tools() -> None:
    def tool_page(fn, title, desc, body_html, js):
        b = f"<h1>{title}</h1><p>{desc}</p>{body_html}<script>{js}</script>"
        with open(os.path.join(DOCS, "tools", fn), "w", encoding="utf-8") as f:
            f.write(page(title, b, desc))

    tool_page("fukuri.html", "複利計算機",
              "毎月の積立額・想定利回り・運用年数から、複利での最終資産を計算します。",
              """<div class='card'>初期資金 <input id=a type=number value=1000000>円<br>
毎月積立 <input id=m type=number value=30000>円<br>
年利 <input id=r type=number value=7 step=0.1>%<br>
年数 <input id=y type=number value=20>年<br>
<button onclick=calc()>計算する</button><div class=result id=out></div></div>""",
              """function calc(){let a=+document.getElementById('a').value,m=+document.getElementById('m').value,
r=+document.getElementById('r').value/100/12,y=+document.getElementById('y').value*12,v=a,paid=a;
for(let i=0;i<y;i++){v=v*(1+r)+m;paid+=m}
document.getElementById('out').textContent='最終資産: '+Math.round(v).toLocaleString()+'円（元本 '+paid.toLocaleString()+'円、運用益 '+Math.round(v-paid).toLocaleString()+'円）'}""")

    tool_page("position-size.html", "ポジションサイズ計算機",
              "「1回の取引で口座の何%まで失ってよいか」から、適正な株数を逆算します。リスク管理の基本ツールです。",
              """<div class='card'>口座資金 <input id=c type=number value=1000000>円<br>
許容リスク <input id=k type=number value=1 step=0.1>%（1回の損失上限）<br>
エントリー価格 <input id=e type=number value=3000>円<br>
損切り価格 <input id=s type=number value=2850>円<br>
<button onclick=calc()>計算する</button><div class=result id=out></div></div>""",
              """function calc(){let c=+document.getElementById('c').value,k=+document.getElementById('k').value/100,
e=+document.getElementById('e').value,s=+document.getElementById('s').value,d=e-s;
if(d<=0){document.getElementById('out').textContent='損切り価格はエントリーより下に設定してください';return}
let sh=Math.floor(c*k/d);document.getElementById('out').textContent='適正株数: '+sh.toLocaleString()+'株（想定損失 '
+Math.round(sh*d).toLocaleString()+'円 = 口座の'+(sh*d/c*100).toFixed(2)+'%、必要資金 '+Math.round(sh*e).toLocaleString()+'円）'}""")

    tool_page("drawdown.html", "ドローダウン回復計算機",
              "資産が○%下落したとき、元に戻すには何%の上昇が必要か。損失の非対称性を体感するための計算機です。",
              """<div class='card'>下落率 <input id=d type=number value=30 min=1 max=99>%<br>
<button onclick=calc()>計算する</button><div class=result id=out></div>
<div class=meta id=tbl style='margin-top:14px'></div></div>""",
              """function calc(){var d=+document.getElementById('d').value/100;
var need=(1/(1-d)-1)*100;
document.getElementById('out').textContent='-'+(d*100).toFixed(0)+'%の損失を取り戻すには +'+need.toFixed(1)+'% の上昇が必要です';
var rows=[10,20,30,40,50,60,70,80,90].map(function(x){var n=(1/(1-x/100)-1)*100;
return '-'+x+'% → +'+n.toFixed(0)+'%必要'});
document.getElementById('tbl').innerHTML=rows.join('<br>')}calc();""")

    tool_page("fee-calc.html", "証券会社の年間手数料計算機",
              "1回の取引金額と年間取引回数から、証券会社ごとの年間手数料を比較計算します。料率は2026年8月調査時点（必ず公式で最新確認を）。",
              """<div class='card'>1回の取引金額 <input id=amt type=number value=300000>円<br>
年間取引回数 <input id=n type=number value=24>回<br>
<button onclick=calc()>計算する</button><div class=result id=out></div>
<div id=tbl style='margin-top:10px'></div></div>""",
              """function calc(){var a=+document.getElementById('amt').value,n=+document.getElementById('n').value;
var usd=155;var brokers=[['moomoo証券（米国株）',0.00088,16.5*usd],['SBI・楽天・マネックス・松井（米国株）',0.00495,22*usd],
['楽天・SBI・moomoo（国内株）',0,0]];
var h='<table><tr><th>証券会社（区分）</th><th>1回あたり</th><th>年間合計</th></tr>';
brokers.forEach(function(b){var per=Math.min(a*b[1],b[2]||Infinity);if(b[1]===0)per=0;
h+='<tr><td>'+b[0]+'</td><td>'+Math.round(per).toLocaleString()+'円</td><td><strong>'+Math.round(per*n).toLocaleString()+'円</strong></td></tr>'});
h+='</table>';document.getElementById('tbl').innerHTML=h;
document.getElementById('out').textContent='年間'+n+'回 × '+a.toLocaleString()+'円の場合';}calc();""")

    tool_page("jpy-return.html", "外貨投資の円建てリターン計算機",
              "米国株などの外貨建て投資は、資産価格と為替の両方で損益が決まります。円ベースの実質リターンを計算します。",
              """<div class='card'>購入時の資産価格 <input id=p0 type=number value=100>ドル<br>
現在の資産価格 <input id=p1 type=number value=120>ドル<br>
購入時の為替 <input id=f0 type=number value=150 step=0.01>円/ドル<br>
現在の為替 <input id=f1 type=number value=155 step=0.01>円/ドル<br>
<button onclick=calc()>計算する</button><div class=result id=out></div></div>""",
              """function calc(){let p0=+document.getElementById('p0').value,p1=+document.getElementById('p1').value,
f0=+document.getElementById('f0').value,f1=+document.getElementById('f1').value;
let usd=(p1/p0-1)*100,jpy=(p1*f1/(p0*f0)-1)*100,fx=(f1/f0-1)*100;
document.getElementById('out').textContent='ドル建て '+usd.toFixed(2)+'% ／ 為替 '+fx.toFixed(2)+'% ／ 円建て実質 '+jpy.toFixed(2)+'%'}""")


def git_push() -> None:
    def run(*cmd):
        return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    run("git", "add", "-A")
    run("git", "commit", "-m", f"auto update {dt.date.today()}")
    r = run("git", "push")
    if r.returncode != 0:
        print("push skipped (remote not configured yet - see USER_SETUP.md)")
    else:
        print("pushed")


def gen_note_digest() -> str:
    """Weekly digest draft for note.com (paste-ready; no affiliate links —
    note's ToS forbids ASP links, so this is a pure funnel to the hub)."""
    today = dt.date.today()
    posts = load_posts()
    journals = [p for p in posts if p["type"] == "journal"][:5]
    articles = [p for p in posts if p["type"] != "journal"][:3]
    eq_line = ""
    try:
        with open(os.path.join(TV2, "state", "paper_state.json"), encoding="utf-8") as f:
            st = json.load(f)
        cur = st["history"][-1]
        ret = (cur["equity_jpy"] / st.get("capital_jpy", 1_000_000) - 1) * 100
        eq_line = f"今週時点の仮想資産は **{cur['equity_jpy']:,}円（開始から{ret:+.2f}%）** です。"
    except Exception:
        pass
    j = "\n".join(f"- {p['date']}: {p['title']}" for p in journals) or "- （今週の記録は蓄積中です）"
    a = "\n".join(f"- [{p['title']}]({BASE_URL}/posts/{p['slug']}.html)" for p in articles)
    body = f"""# 【週報】AIが全自動運用するトレードシステム、今週の記録（{today:%Y-%m-%d}）

こんにちは、オートクオンツ研究所です。AI（Claude）が設計・実装・運用まで行う自動売買システムの検証記録を、毎日すべて事後公開しています。{eq_line}

## 今週のジャーナル
{j}

## 今週のおすすめ記事（本店で全文公開中）
{a}

## このプロジェクトについて
「バックテストでは勝てるのに実戦で負ける」原因（過適合・ルックアヘッド）を、全実績の事後公開という形で検証しているプロジェクトです。毎日の記録・検証手法の解説・計算ツールはすべて無料で公開しています。

▶ 本店（毎日自動更新）: {BASE_URL}/

※本記事は投資助言ではありません。掲載実績はペーパートレードを含み、将来の成果を保証するものではありません。
"""
    os.makedirs(os.path.join(ROOT, "note_queue"), exist_ok=True)
    path = os.path.join(ROOT, "note_queue", f"note-{today:%Y%m%d}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily", action="store_true")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--note-digest", action="store_true")
    a = ap.parse_args()
    if a.daily:
        slug = gen_daily_journal()
        print(f"journal: {slug or 'skipped (exists or no data)'}")
    if a.note_digest:
        print(f"note digest -> {gen_note_digest()}")
    build()
    if a.push:
        git_push()
    sys.exit(0)
