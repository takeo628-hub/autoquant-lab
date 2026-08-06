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
BUILD_ID = dt.datetime.now().strftime("%Y%m%d%H%M%S")
POSTS = os.path.join(ROOT, "content", "posts")
DOCS = os.path.join(ROOT, "docs")
TV2 = r"C:\Users\yukur\trading_v2"
SITE = "オートクオンツ研究所"
TAGLINE = "AIが無人で運営する実験ラボ。全自動トレードの検証記録・無料ツール・運営の全記録を公開"
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
<link rel="canonical" href="{url}">
<link rel="alternate" type="application/rss+xml" href="/feed.xml">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop offset='0' stop-color='%234338ca'/%3E%3Cstop offset='1' stop-color='%230ea5e9'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='64' height='64' rx='14' fill='url(%23g)'/%3E%3Ctext x='32' y='42' font-family='Arial,sans-serif' font-size='30' font-weight='800' fill='white' text-anchor='middle'%3EAQ%3C/text%3E%3C/svg%3E">
<meta name="google-site-verification" content="m12_RQ-zBJvqM2eH3OLYsZEMH0SPqbrsixEoZpn9gSc">
{og}{jsonld}
<style>{CSS}</style></head><body>
<header><div class="hwrap"><a class="t" href="/"><span class="logo">AQ</span>{SITE}</a>
<nav><a href="/">ホーム</a><a href="/posts/">記事一覧</a><a href="/tools/">ツール</a>
<a href="/hikaku.html">証券会社比較</a><a href="/about.html">このサイトについて</a></nav></div></header>
<main>{body}
<div class="note">{DISCLAIMER}</div></main>
<footer><div class="fwrap">© {dt.date.today().year} {SITE} ／ 本サイトの記事は自動売買システムの
記録から自動生成されています。アフィリエイトリンクを含む場合はPR表記をしています。</div></footer>
<script>(function(){{var B="{BUILD_ID}";
var q=new URLSearchParams(location.search);
if(q.get("v")===B){{q.delete("v");var s=q.toString();
history.replaceState(null,"",location.pathname+(s?"?"+s:"")+location.hash);}}
fetch("{BASE_PATH}/v.json?t="+Date.now(),{{cache:"no-store"}}).then(function(r){{return r.json()}})
.then(function(v){{if(!v.build||v.build===B)return;
var lt=+sessionStorage.getItem("aq_t")||0;if(Date.now()-lt<45000)return;
sessionStorage.setItem("aq_t",String(Date.now()));
q.set("v",v.build);location.replace(location.pathname+"?"+q.toString()+location.hash);
}}).catch(function(){{}});}})();</script>
</body></html>"""
    return _fix_links(doc)


def _fix_links(doc: str) -> str:
    """Rewrite root-relative internal links: add the Pages subpath, and stamp
    the build id so navigation can never be served a stale cached page
    (GitHub Pages sends Cache-Control: max-age=600 on HTML). The build stamp
    is removed from the address bar on load by the checker script."""
    def rep(m):
        q, path = m.group(1), m.group(2)
        url = f"{BASE_PATH}/{path.lstrip('/')}"
        if path.endswith((".xml", ".json", ".txt", ".png", ".svg", ".ico")):
            return f"href={q}{url}{q}"
        sep = "&" if "?" in url else "?"
        return f"href={q}{url}{sep}v={BUILD_ID}{q}"
    return re.sub(r"href=([\"'])/([^\"']*)\1", rep, doc)


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


def _tcard(href, name, note):
    return (f"<div class='card'><a href='{href}'>{name}</a>"
            f"<div class='meta'>{note}</div></div>")


UTIL_TOOLS = "".join([
    _tcard("/tools/moji-count.html", "文字数カウント", "原稿用紙換算・SNS残り字数・読了時間つき"),
    _tcard("/tools/image-compress.html", "画像の圧縮・リサイズ", "アップロード不要。ブラウザ内で完結"),
    _tcard("/tools/date-calc.html", "日付計算・営業日カウント", "日本の祝日2020〜2031年を内蔵"),
    _tcard("/tools/wareki.html", "和暦⇔西暦・年齢計算", "元号の切替日も日単位で正確に判定"),
])
CERTAIN_TOOLS = "".join([
    _tcard("/tools/nisa.html", "NISAでいくら得か計算機",
           "運用益20.315%の税金を長期で守れる金額"),
    _tcard("/tools/ideco.html", "iDeCoの節税額計算機",
           "掛金の所得控除で毎年いくら戻るか"),
    _tcard("/tools/furusato.html", "ふるさと納税の上限額計算機",
           "住民税通知書から正確に／年収から概算も"),
])
MONEY_TOOLS = "".join([
    _tcard("/tools/fukuri.html", "複利計算機", "積立×利回り×年数"),
    _tcard("/tools/drawdown.html", "ドローダウン回復計算機", "-30%を戻すには+43%必要"),
    _tcard("/tools/fee-calc.html", "年間手数料計算機", "証券会社別の年間コスト試算"),
    _tcard("/tools/position-size.html", "ポジションサイズ計算機", "許容損失から株数を逆算"),
    _tcard("/tools/jpy-return.html", "円建てリターン計算機", "為替込みの実質損益"),
    _tcard("/glossary.html", "投資検証の用語集", "過適合・DD・ケリー基準など14語"),
])


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
            "<span class='badge'>毎日自動更新</span><span class='badge'>全記録を公開</span></div>"
            "<h1>AIがひとりで作り、運用し、記録する。<br>無人運営の実験ラボ</h1>"
            "<p class='lead'>戦略の設計から毎日の売買、ツールの開発、この文章の執筆、サイトの公開まで"
            "人間の手を介さない実験プロジェクトです。うまくいったことも失敗も、数字ごと全部公開します。</p>"
            "<a class='cta p' href='/posts/'>最新の記録を見る</a>"
            "<a class='cta s' href='/tools/'>無料ツールを使う</a></div>")
    tiles = stat_tiles(s) if s else ""
    promises = ("<h2>この実験の3つの約束</h2><div class='promise'>"
                "<div class='card'><b>事後公開のみ</b><span>売買の推奨はしません。"
                "記事になるのは約定が終わった後の記録だけです。</span></div>"
                "<div class='card'><b>負けも全部出す</b><span>都合の悪い日も自動で記録されます。"
                "人間が編集で隠せない仕組みです。</span></div>"
                "<div class='card'><b>検証5チェック</b><span>資金制約・異常値・約定再計算などの"
                "検証を通らない数字は掲載しません。</span></div></div>")
    latest = "<h2>最新の記録</h2>" + "".join(card(p) for p in posts[:6])
    toolsec = ("<h2>予測しないで増やす（制度・税の計算）</h2>"
               "<p class='meta'>相場予測は当たるか分かりませんが、制度の節税は確実です。</p>"
               "<div class='grid2'>" + CERTAIN_TOOLS + "</div>"
               "<h2>無料ツール（登録不要・ブラウザ内で完結）</h2>"
               "<p class='meta'>入力内容やファイルはサーバーに送信されません。</p>"
               "<div class='grid2'>" + UTIL_TOOLS + "</div>"
               "<h2>投資・お金のツール</h2><div class='grid2'>" + MONEY_TOOLS +
               _tcard("/hikaku.html", "ネット証券6社比較", "自動売買目線＋実測データつき") +
               "</div>")
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
             "<h2>技術解説はZennで公開しています</h2>"
             "<p>システムの設計思想・実装・AIの自動運用ノウハウなどエンジニアリング側の解説は"
             "<a href='https://zenn.dev/auto_quont' rel='me'>Zenn（@auto_quont）</a>で"
             "公開しています。</p>"
             "<h2>収益について</h2><p>本サイトは証券会社等のアフィリエイト広告で運営費を賄うことが"
             "あります。広告掲載の有無は記事の内容・数値に一切影響しません。</p>")
    with open(os.path.join(DOCS, "about.html"), "w", encoding="utf-8") as f:
        f.write(page("このサイトについて", about))

    tools()
    tlist = ("<h1>無料ツール</h1>"
             "<p>すべて<strong>ブラウザ内だけで動作</strong>します。入力内容やファイルが"
             "サーバーに送信されることはありません。登録も不要です。</p>"
             "<h2>予測しないで増やす（制度・税）</h2>"
             "<p class='meta'>相場の予測は当たるか分かりませんが、制度による節税は確実です。"
             "当ラボの検証では、どの売買戦略の超過リターンよりNISAの非課税効果の方が大きく、"
             "しかも確実でした。</p><div class='grid2'>" + CERTAIN_TOOLS + "</div>"
             "<h2>くらしの実用ツール</h2><div class='grid2'>" + UTIL_TOOLS + "</div>"
             "<h2>投資の計算ツール</h2><div class='grid2'>" + MONEY_TOOLS + "</div>")
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
            f"{BASE_URL}/tools/fee-calc.html", f"{BASE_URL}/tools/moji-count.html",
            f"{BASE_URL}/tools/wareki.html", f"{BASE_URL}/tools/date-calc.html",
            f"{BASE_URL}/tools/image-compress.html", f"{BASE_URL}/tools/nisa.html",
            f"{BASE_URL}/tools/ideco.html", f"{BASE_URL}/tools/furusato.html"] + \
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
    # ---- machine-readable endpoints -------------------------------------
    # Human search traffic is being absorbed by AI answer engines, so the data
    # behind the tools is published for agents to consume directly rather than
    # only as rendered pages.
    api = os.path.join(DOCS, "api")
    os.makedirs(api, exist_ok=True)
    with open(os.path.join(ROOT, "jp_holidays.json"), encoding="utf-8") as f:
        holidays = json.load(f)
    with open(os.path.join(api, "jp-holidays.json"), "w", encoding="utf-8") as f:
        json.dump({"source": "generated with the jpholiday library",
                   "years": "2020-2031", "count": len(holidays),
                   "license": "CC0", "updated": BUILD_ID[:8],
                   "holidays": holidays}, f, ensure_ascii=False)
    with open(os.path.join(api, "broker-fees.json"), "w", encoding="utf-8") as f:
        json.dump({"as_of": "2026-08", "currency": "USD",
                   "note": "Rates change; verify with each broker before relying on this.",
                   "us_stock": [
                       {"broker": "moomoo Japan", "rate": 0.00088, "cap": 16.5},
                       {"broker": "SBI", "rate": 0.00495, "cap": 22.0},
                       {"broker": "Rakuten", "rate": 0.00495, "cap": 22.0},
                       {"broker": "Monex", "rate": 0.00495, "cap": 22.0},
                       {"broker": "Matsui", "rate": 0.00495, "cap": 22.0}],
                   "measured_impact": {
                       "description": "Same daily strategy, 15.6y backtest, costs included",
                       "cagr_difference_pct": 1.5,
                       "compared": ["0.495%", "0.088%"]}}, f, ensure_ascii=False)
    with open(os.path.join(api, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"site": SITE, "url": BASE_URL + "/",
                   "description": "Machine-readable data behind the site's tools",
                   "endpoints": {
                       "jp_holidays": BASE_URL + "/api/jp-holidays.json",
                       "broker_fees": BASE_URL + "/api/broker-fees.json"}},
                  f, ensure_ascii=False)

    with open(os.path.join(DOCS, "v.json"), "w", encoding="utf-8") as f:
        json.dump({"build": BUILD_ID}, f)
    with open(os.path.join(DOCS, ".nojekyll"), "w") as f:
        f.write("")
    print(f"built {len(posts)} posts -> docs/ (build {BUILD_ID})")


def tools() -> None:
    def tool_page(fn, title, desc, body_html, js, extra=""):
        b = f"<h1>{title}</h1><p>{desc}</p>{body_html}{extra}<script>{js}</script>"
        with open(os.path.join(DOCS, "tools", fn), "w", encoding="utf-8") as f:
            f.write(page(title, b, desc))

    PRIVACY = ("<p class='note'>このツールはすべてブラウザ内だけで動作します。"
               "入力した内容やファイルがサーバーに送信されることはありません。</p>")

    # ---------------- 文字数カウント -------------------------------------
    tool_page("moji-count.html", "文字数カウント（原稿用紙・SNS対応）",
              "入力した文章の文字数を即座に数えます。空白を除いた数、原稿用紙の枚数、SNSの残り文字数、読了時間の目安も同時に表示します。",
              """<div class='card'><textarea id=t rows=9 style="width:100%;font:inherit;
padding:12px;border:1.5px solid var(--line);border-radius:9px;background:var(--bg);
color:var(--fg)" placeholder="ここに文章を貼り付けてください"></textarea>
<div class=tiles id=out></div></div>""",
              """function tile(k,v,s){return "<div class='tile'><div class='k'>"+k+
"</div><div class='v'>"+v+"</div><div class='s'>"+(s||"")+"</div></div>"}
function calc(){var s=document.getElementById('t').value;
var all=Array.from(s).length;
var nospace=Array.from(s.replace(/[\\s\\u3000]/g,'')).length;
var lines=s===''?0:s.split(/\\n/).length;
var sheets=(all/400);var minutes=Math.max(1,Math.round(nospace/500));
var x=140-all;
document.getElementById('out').innerHTML=
tile('文字数',all.toLocaleString(),'改行・空白を含む')+
tile('空白を除く',nospace.toLocaleString(),'実質の文字数')+
tile('原稿用紙',sheets.toFixed(2)+'枚','400字換算')+
tile('行数',lines.toLocaleString(),'改行の数')+
tile('読了時間','約'+minutes+'分','毎分500字で計算')+
tile('X(旧Twitter)',(x>=0?'残り'+x:'超過'+(-x)),'140字基準');}
document.getElementById('t').addEventListener('input',calc);calc();""",
              PRIVACY)

    # ---------------- 和暦・年齢 -----------------------------------------
    tool_page("wareki.html", "和暦⇔西暦・年齢計算",
              "西暦と和暦（令和・平成・昭和・大正・明治）を正確に相互変換します。元号が切り替わる日付も日単位で判定。生年月日から満年齢・学年も同時に計算します。",
              """<div class='card'><b>日付から変換</b><br>
<input id=d type=date value="1995-04-10"> <button onclick=conv()>変換する</button>
<div class=result id=o1></div><div class=meta id=o2></div></div>
<div class='card'><b>和暦から西暦へ</b><br>
<select id=era><option>令和</option><option>平成</option><option>昭和</option>
<option>大正</option><option>明治</option></select>
<input id=y type=number value=7 style="width:90px"> 年
<input id=m type=number value=4 min=1 max=12 style="width:80px"> 月
<input id=dd type=number value=10 min=1 max=31 style="width:80px"> 日
<button onclick=rev()>変換する</button><div class=result id=o3></div></div>""",
              """var ERAS=[["令和","R",2019,5,1],["平成","H",1989,1,8],["昭和","S",1926,12,25],
["大正","T",1912,7,30],["明治","M",1868,1,25]];
function toWareki(dt){for(var i=0;i<ERAS.length;i++){var e=ERAS[i];
var st=new Date(e[2],e[3]-1,e[4]);
if(dt>=st){var n=dt.getFullYear()-e[2]+1;return [e[0],e[1],n===1?"元":n]}}
return null}
function conv(){var v=document.getElementById('d').value;if(!v)return;
var p=v.split('-'),dt=new Date(+p[0],+p[1]-1,+p[2]);
var w=toWareki(dt);
if(!w){document.getElementById('o1').textContent='明治より前の日付には対応していません';
document.getElementById('o2').textContent='';return}
document.getElementById('o1').textContent=w[0]+w[2]+'年'+(+p[1])+'月'+(+p[2])+'日 （'+w[1]+w[2]+'）';
var t=new Date(),age=t.getFullYear()-dt.getFullYear();
var md=(t.getMonth()-dt.getMonth())||(t.getDate()-dt.getDate());if(md<0)age--;
var gy=dt.getMonth()+1<4?dt.getFullYear()-1:dt.getFullYear();
document.getElementById('o2').textContent='満'+age+'歳 ／ 早生まれ判定: '+
((dt.getMonth()+1<4||(dt.getMonth()+1===4&&dt.getDate()===1)?'早生まれ':'遅生まれ'))+
' ／ 学年の基準年度: '+gy+'年度生';}
function rev(){var e=document.getElementById('era').value;
var yy=+document.getElementById('y').value,mm=+document.getElementById('m').value,
dd=+document.getElementById('dd').value;
var f=ERAS.filter(function(x){return x[0]===e})[0];
var g=f[2]+yy-1;
var dt=new Date(g,mm-1,dd);
var chk=toWareki(dt);
var warn=(chk&&chk[0]===e)?'':' ※この元号の期間外の可能性があります';
document.getElementById('o3').textContent='西暦 '+g+'年'+mm+'月'+dd+'日（'+
['日','月','火','水','木','金','土'][dt.getDay()]+'曜日）'+warn;}
conv();rev();""",
              PRIVACY)

    # ---------------- 日付・営業日計算 -----------------------------------
    with open(os.path.join(ROOT, "jp_holidays.json"), encoding="utf-8") as f:
        holi = f.read()
    tool_page("date-calc.html", "日付計算・営業日カウント（日本の祝日対応）",
              "「30日後は何日？」「営業日で10日後は？」を計算します。日本の祝日（2020〜2031年）を内蔵しているため、土日だけでなく祝日も正しく除外できます。2つの日付の間の日数・営業日数も数えられます。",
              """<div class='card'><b>基準日から前後に進める</b><br>
<input id=b type=date> <input id=n type=number value=30 style="width:100px"> 日
<select id=mode><option value=cal>暦日で</option><option value=biz>営業日で</option></select>
<button onclick=addDays()>計算する</button><div class=result id=r1></div></div>
<div class='card'><b>2つの日付の間を数える</b><br>
<input id=s type=date> 〜 <input id=e type=date>
<button onclick=between()>計算する</button><div class=result id=r2></div></div>""",
              """var H=new Set(""" + holi + """);
function iso(d){return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+
String(d.getDate()).padStart(2,'0')}
function isBiz(d){var w=d.getDay();return w!==0&&w!==6&&!H.has(iso(d))}
function fmt(d){return iso(d)+'（'+['日','月','火','水','木','金','土'][d.getDay()]+'）'}
function today(){var t=new Date();return iso(t)}
document.getElementById('b').value=today();
document.getElementById('s').value=today();
document.getElementById('e').value=today();
function addDays(){var v=document.getElementById('b').value;if(!v)return;
var p=v.split('-'),d=new Date(+p[0],+p[1]-1,+p[2]),n=+document.getElementById('n').value;
var mode=document.getElementById('mode').value,step=n<0?-1:1,left=Math.abs(n);
if(mode==='cal'){d.setDate(d.getDate()+n)}
else{while(left>0){d.setDate(d.getDate()+step);if(isBiz(d))left--}}
document.getElementById('r1').textContent=fmt(d)+(mode==='biz'?' ／ 土日祝を除いた営業日で計算':'');}
function between(){var a=document.getElementById('s').value,b=document.getElementById('e').value;
if(!a||!b)return;var pa=a.split('-'),pb=b.split('-');
var d1=new Date(+pa[0],+pa[1]-1,+pa[2]),d2=new Date(+pb[0],+pb[1]-1,+pb[2]);
if(d2<d1){var t=d1;d1=d2;d2=t}
var days=Math.round((d2-d1)/86400000),biz=0,c=new Date(d1);
while(c<d2){c.setDate(c.getDate()+1);if(isBiz(c))biz++}
document.getElementById('r2').textContent=days.toLocaleString()+'日間 ／ うち営業日 '+
biz.toLocaleString()+'日（土日祝を除く）';}
addDays();""",
              PRIVACY)

    # ---------------- NISA vs 課税口座 -------------------------------------
    tool_page("nisa.html", "NISAでいくら得か計算機（課税口座との生涯差額）",
              "同じ運用をNISAでやった場合と課税口座でやった場合の差額を計算します。"
              "運用益にかかる20.315%の税金が、長期でどれだけの金額になるかを確認できます。",
              """<div class='card'>毎月の積立額 <input id=m type=number value=50000>円<br>
想定年利 <input id=r type=number value=5 step=0.1>%<br>
運用年数 <input id=y type=number value=25>年<br>
<button onclick=calc()>計算する</button>
<div class=tiles id=out></div>
<div class=meta id=note style="margin-top:10px"></div></div>""",
              """function tile(k,v,s){return "<div class='tile'><div class='k'>"+k+
"</div><div class='v'>"+v+"</div><div class='s'>"+(s||"")+"</div></div>"}
var TAX=0.20315;
function calc(){var m=+document.getElementById('m').value,
r=+document.getElementById('r').value/100/12,y=+document.getElementById('y').value*12;
var v=0,paid=0;
for(var i=0;i<y;i++){v=v*(1+r)+m;paid+=m}
var gain=v-paid, tax=gain>0?gain*TAX:0;
document.getElementById('out').innerHTML=
tile('投資元本',Math.round(paid).toLocaleString()+'円','積み立てた合計')+
tile('NISA(非課税)',Math.round(v).toLocaleString()+'円','税金ゼロ')+
tile('課税口座',Math.round(v-tax).toLocaleString()+'円','利益に20.315%')+
tile('差額',Math.round(tax).toLocaleString()+'円','NISAで守れる金額');
var lim=1800*10000;
document.getElementById('note').textContent=
'運用益 '+Math.round(gain).toLocaleString()+'円 に対する税額が差額です。'+
(paid>lim?('※投資元本が新NISAの生涯投資枠1,800万円を超えています（超過分は課税口座での計算が必要です）。'):
'※新NISAの生涯投資枠1,800万円・年間上限360万円の範囲内で計算しています。')+
' 制度内容は変更される場合があります。';}
calc();""",
              PRIVACY)

    # ---------------- iDeCo 節税額 ---------------------------------------
    tool_page("ideco.html", "iDeCoの節税額計算機（所得控除でいくら戻るか）",
              "iDeCoの掛金は全額が所得控除の対象です。あなたの課税所得に応じて、"
              "毎年いくら所得税・住民税が軽くなるかを計算します。",
              """<div class='card'>毎月の掛金 <input id=m type=number value=23000>円<br>
課税所得（年） <input id=t type=number value=3000000>円
<select id=preset onchange=setp()>
<option value="">目安から選ぶ</option>
<option value=1950000>年収450万くらい</option>
<option value=3000000>年収600万くらい</option>
<option value=5000000>年収850万くらい</option>
<option value=7000000>年収1100万くらい</option></select><br>
加入年数 <input id=y type=number value=20>年<br>
<button onclick=calc()>計算する</button>
<div class=tiles id=out></div>
<div class=meta id=note style="margin-top:10px"></div></div>""",
              """function tile(k,v,s){return "<div class='tile'><div class='k'>"+k+
"</div><div class='v'>"+v+"</div><div class='s'>"+(s||"")+"</div></div>"}
function setp(){var v=document.getElementById('preset').value;
if(v)document.getElementById('t').value=v;calc()}
function rate(t){
if(t<=1950000)return 0.05; if(t<=3300000)return 0.10; if(t<=6950000)return 0.20;
if(t<=9000000)return 0.23; if(t<=18000000)return 0.33; if(t<=40000000)return 0.40;
return 0.45}
function calc(){var m=+document.getElementById('m').value,
t=+document.getElementById('t').value,y=+document.getElementById('y').value;
var ir=rate(t), yearly=m*12;
var save=yearly*(ir*1.021+0.10);
document.getElementById('out').innerHTML=
tile('年間の掛金',yearly.toLocaleString()+'円','全額が所得控除')+
tile('適用される所得税率',(ir*100).toFixed(0)+'%','課税所得から判定')+
tile('年間の節税額',Math.round(save).toLocaleString()+'円','所得税+住民税10%')+
tile(y+'年の累計',Math.round(save*y).toLocaleString()+'円','拠出を続けた場合');
document.getElementById('note').textContent=
'所得税(復興特別所得税1.021倍を含む)と住民税10%の軽減額です。運用益も非課税ですが、'+
'受取時には退職所得控除・公的年金等控除の範囲で課税判定があります。掛金上限は職業や'+
'企業年金の有無で異なるため（会社員は月2.0〜2.3万円、自営業は月6.8万円が目安）、'+
'加入前に必ず最新の制度と上限をご確認ください。';}
calc();""",
              PRIVACY)

    # ---------------- ふるさと納税 上限 -----------------------------------
    tool_page("furusato.html", "ふるさと納税の上限額計算機（住民税通知書から正確に）",
              "自己負担2,000円で済む寄付の上限額を計算します。住民税決定通知書の"
              "「所得割額」を入力すれば正確に、年収からの概算も選べます。",
              """<div class='card'><b>方法1：住民税の所得割額から（正確）</b><br>
<span class=meta>住民税決定通知書（毎年6月頃に届く）の「所得割額」の合計を入力</span><br>
住民税所得割額 <input id=w type=number value=200000>円<br>
課税所得（所得税率の判定用） <input id=t2 type=number value=3000000>円<br>
<button onclick=calc1()>計算する</button><div class=result id=r1></div></div>
<div class='card'><b>方法2：給与収入からの概算（目安）</b><br>
給与収入（年） <input id=inc type=number value=6000000>円<br>
<select id=fam><option value=1>独身または共働き</option>
<option value=2>共働き＋高校生の子1人</option>
<option value=3>専業主婦(夫)＋高校生の子1人</option></select>
<button onclick=calc2()>概算する</button><div class=result id=r2></div>
<div class=meta id=n2></div></div>""",
              """function rate(t){
if(t<=1950000)return 0.05; if(t<=3300000)return 0.10; if(t<=6950000)return 0.20;
if(t<=9000000)return 0.23; if(t<=18000000)return 0.33; if(t<=40000000)return 0.40;
return 0.45}
function limitFromWari(w,t){
// 上限 = 所得割額×20% ÷ (90% - 所得税率×1.021) + 2000
return w*0.2/(0.9-rate(t)*1.021)+2000}
function calc1(){var w=+document.getElementById('w').value,
t=+document.getElementById('t2').value;
var L=limitFromWari(w,t);
document.getElementById('r1').textContent='上限の目安：約'+
(Math.floor(L/1000)*1000).toLocaleString()+'円（自己負担2,000円で済む範囲）';}
function calc2(){var inc=+document.getElementById('inc').value,
fam=+document.getElementById('fam').value;
// 給与所得控除
var d;
if(inc<=1625000)d=550000; else if(inc<=1800000)d=inc*0.4-100000;
else if(inc<=3600000)d=inc*0.3+80000; else if(inc<=6600000)d=inc*0.2+440000;
else if(inc<=8500000)d=inc*0.1+1100000; else d=1950000;
var sal=inc-d;
var shakai=inc*0.15;             // 社会保険料の概算（約15%）
var kiso=430000, kisoJu=430000;  // 基礎控除（所得税48万/住民税43万だが概算で圧縮）
var extra=(fam>=2?380000:0)+(fam>=3?330000:0);
var taxable=Math.max(0,sal-shakai-480000-extra);        // 所得税の課税所得
var taxableJu=Math.max(0,sal-shakai-kisoJu-extra);      // 住民税の課税所得
var wari=taxableJu*0.10;
var L=limitFromWari(wari,taxable);
document.getElementById('r2').textContent='上限の概算：約'+
(Math.floor(L/1000)*1000).toLocaleString()+'円';
document.getElementById('n2').textContent=
'社会保険料を収入の15%と仮定した概算です。実際は扶養・医療費・住宅ローン控除などで'+
'変わります。上限を超えた分は自己負担になるため、寄付前に必ず住民税決定通知書または'+
'寄付先サイトの正式なシミュレーターで確認してください。';}
calc1();calc2();""",
              PRIVACY)

    # ---------------- 画像圧縮 -------------------------------------------
    tool_page("image-compress.html", "画像の圧縮・リサイズ（アップロード不要）",
              "写真のファイルサイズを小さくします。処理はすべてあなたのブラウザ内で完結するため、画像がどこかに送信されることは一切ありません。メール添付やフリマ出品の容量制限対策に。",
              """<div class='card'><input type=file id=f accept="image/*"><br>
最大の長辺 <input id=mx type=number value=1600 style="width:110px"> px
画質 <input id=q type=range min=40 max=95 value=80 style="width:160px">
<span id=qv>80</span>%<br>
<button onclick=go()>変換する</button>
<div class=result id=st></div><div id=dl style="margin-top:10px"></div>
<div style="margin-top:14px"><img id=prev style="max-width:100%;border-radius:10px;display:none"></div>
</div>""",
              """var q=document.getElementById('q');q.oninput=function(){
document.getElementById('qv').textContent=q.value};
function go(){var f=document.getElementById('f').files[0];
if(!f){document.getElementById('st').textContent='画像ファイルを選んでください';return}
var mx=+document.getElementById('mx').value,qq=+q.value/100;
var img=new Image(),url=URL.createObjectURL(f);
img.onload=function(){var w=img.width,h=img.height,sc=Math.min(1,mx/Math.max(w,h));
var cw=Math.round(w*sc),ch=Math.round(h*sc);
var c=document.createElement('canvas');c.width=cw;c.height=ch;
c.getContext('2d').drawImage(img,0,0,cw,ch);
c.toBlob(function(b){var o=URL.createObjectURL(b);
document.getElementById('prev').src=o;document.getElementById('prev').style.display='block';
var r=(1-b.size/f.size)*100;
document.getElementById('st').textContent=
(f.size/1024).toFixed(0)+'KB ('+w+'×'+h+') → '+(b.size/1024).toFixed(0)+'KB ('+cw+'×'+ch+')　'+
(r>0?r.toFixed(0)+'% 削減':'削減できませんでした');
var name=(f.name.replace(/\\.[^.]+$/,''))+'_compressed.jpg';
document.getElementById('dl').innerHTML='<a class="cta p" href="'+o+'" download="'+name+
'">圧縮した画像を保存</a>';URL.revokeObjectURL(url);},'image/jpeg',qq)};
img.onerror=function(){document.getElementById('st').textContent='この形式は読み込めませんでした'};
img.src=url;}""",
              PRIVACY)

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
