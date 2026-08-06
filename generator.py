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
:root{--bg:#fff;--fg:#1a1a1a;--sub:#555;--line:#e5e5e5;--acc:#0b5fff;--box:#f6f8fa}
@media(prefers-color-scheme:dark){:root{--bg:#111417;--fg:#e8e8e8;--sub:#9aa;--line:#2a2f35;--acc:#6ea8ff;--box:#1a1f24}}
*{box-sizing:border-box}body{margin:0;font-family:'Hiragino Sans','Yu Gothic UI',Meiryo,sans-serif;
background:var(--bg);color:var(--fg);line-height:1.9}
main{max-width:760px;margin:0 auto;padding:24px 16px 64px}
header{border-bottom:1px solid var(--line)}
.hwrap{max-width:760px;margin:0 auto;padding:14px 16px;display:flex;gap:16px;align-items:baseline;flex-wrap:wrap}
.hwrap a{color:var(--fg);text-decoration:none}.hwrap .t{font-weight:700;font-size:18px}
nav a{color:var(--sub);text-decoration:none;margin-right:14px;font-size:14px}
h1{font-size:26px;line-height:1.5}h2{font-size:20px;margin-top:2em;border-left:4px solid var(--acc);padding-left:10px}
h3{font-size:17px}a{color:var(--acc)}
table{border-collapse:collapse;width:100%;font-size:14px;display:block;overflow-x:auto}
th,td{border:1px solid var(--line);padding:6px 10px;text-align:right}th:first-child,td:first-child{text-align:left}
.meta{color:var(--sub);font-size:13px}
.note{background:var(--box);border:1px solid var(--line);border-radius:8px;padding:12px 16px;font-size:13px;color:var(--sub);margin-top:40px}
.pr{background:var(--box);border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin:24px 0}
.pr .tag{font-size:11px;color:var(--sub);letter-spacing:.1em}
.card{border:1px solid var(--line);border-radius:8px;padding:14px 16px;margin:12px 0}
.card a{text-decoration:none;font-weight:600}
input,select{font:inherit;padding:6px 8px;margin:4px 0;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg)}
button{font:inherit;padding:8px 16px;border:0;border-radius:6px;background:var(--acc);color:#fff;cursor:pointer}
.result{font-size:18px;font-weight:700;margin-top:12px}
footer{border-top:1px solid var(--line);margin-top:48px}
.fwrap{max-width:760px;margin:0 auto;padding:20px 16px;font-size:12px;color:var(--sub)}
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
<header><div class="hwrap"><a class="t" href="/">{SITE}</a>
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

## 現在の状態
| 項目 | 値 |
| --- | --- |
| 仮想資産 | {cur['equity_jpy']:,}円 |
| 開始からの損益 | {ret:+.2f}% |
| 現金 | {cur['cash']:,.0f}円 |

保有: {pos_s}

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


# ---------------------------------------------------------------- build
def build() -> None:
    os.makedirs(os.path.join(DOCS, "posts"), exist_ok=True)
    os.makedirs(os.path.join(DOCS, "tools"), exist_ok=True)
    posts = load_posts()
    aff = affiliate_box()

    chart = svg_equity()
    for p in posts:
        rendered = md2html(p["body"]).replace("<p>::EQUITY_CHART::</p>", chart)
        others = [q for q in posts if q["slug"] != p["slug"]][:3]
        rel = ("<h2>関連記事</h2>" + "".join(
            f"<div class='card'><a href='/posts/{q['slug']}.html'>"
            f"{html.escape(q['title'])}</a><div class='meta'>{q['date']}</div></div>"
            for q in others)) if others else ""
        body = (f"<h1>{html.escape(p['title'])}</h1><div class='meta'>{p['date']}・"
                f"{'検証ジャーナル' if p['type'] == 'journal' else '解説記事'}</div>"
                + rendered + aff + rel)
        meta = {"url": f"{BASE_URL}/posts/{p['slug']}.html", "date": p["date"]}
        with open(os.path.join(DOCS, "posts", p["slug"] + ".html"), "w", encoding="utf-8") as f:
            f.write(page(p["title"], body, p["desc"], meta))

    plist = "".join(f"<div class='card'><a href='/posts/{p['slug']}.html'>{html.escape(p['title'])}</a>"
                    f"<div class='meta'>{p['date']}</div></div>" for p in posts)
    with open(os.path.join(DOCS, "posts", "index.html"), "w", encoding="utf-8") as f:
        f.write(page("記事一覧", f"<h1>記事一覧</h1>{plist}"))

    latest = posts[:6]
    llist = "".join(f"<div class='card'><a href='/posts/{p['slug']}.html'>{html.escape(p['title'])}</a>"
                    f"<div class='meta'>{p['date']}</div></div>" for p in latest)
    intro = (f"<h1>{SITE}</h1><p>{TAGLINE}。人間の裁量を排した自動売買システムが毎日ここに記録を"
             "残します。バックテストの嘘（過適合・ルックアヘッド）を検証で暴きながら、"
             "本物の期待値だけを積み上げる実験です。</p>"
             "<h2>最新の記録</h2>" + llist +
             "<h2>計算ツール</h2><div class='card'><a href='/tools/fukuri.html'>複利計算機</a>"
             "<div class='meta'>積立×利回り×年数のシミュレーション</div></div>"
             "<div class='card'><a href='/tools/position-size.html'>ポジションサイズ計算機</a>"
             "<div class='meta'>許容損失から適正な株数を逆算</div></div>"
             "<div class='card'><a href='/tools/jpy-return.html'>外貨投資の円建てリターン計算機</a>"
             "<div class='meta'>為替込みの実質損益を計算</div></div>")
    with open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8") as f:
        f.write(page("ホーム", intro + aff, TAGLINE))

    hikaku = ("<h1>証券会社の手数料比較 — 当ラボの実測データつき</h1>"
              "<p>証券会社選びで最も確実に効くのは手数料です。予測が当たるかは不確実ですが、"
              "コストは100%確実にリターンから引かれます。当ラボの検証エンジンで実測した影響と"
              "あわせて比較します（手数料は改定されることがあります。申込前に必ず公式サイトで"
              "最新の料率をご確認ください。2026年8月時点の調査に基づきます）。</p>"
              "<h2>米国株の取引手数料</h2>"
              "<table><tr><th>証券会社</th><th>米国株手数料</th><th>上限</th></tr>"
              "<tr><td>moomoo証券</td><td>約定代金の0.088%（税込）</td><td>16.5ドル</td></tr>"
              "<tr><td>楽天証券</td><td>約定代金の0.495%（税込）</td><td>22ドル</td></tr></table>"
              "<h2>当ラボの実測：手数料差は年率でどれだけ効くか</h2>"
              "<p>同一の売買ルール（15.6年・コスト込みバックテスト）を手数料率だけ変えて回した"
              "結果、0.495%と0.088%の差は<strong>年率およそ1.5%</strong>の成績差になりました。"
              "複利で15年続くと最終資産で数十%の差です。売買頻度が高い運用ほど差は拡大します。</p>"
              "<h2>国内株について</h2>"
              "<p>楽天証券は「ゼロコース」で国内株の売買手数料が0円です。当ラボの日本株検証でも"
              "この前提を使用しています。</p>" + aff +
              "<p class='meta'>本ページには広告リンクを含む場合があります（PR表記のあるもの）。"
              "掲載の有無は比較内容・数値に影響しません。</p>")
    with open(os.path.join(DOCS, "hikaku.html"), "w", encoding="utf-8") as f:
        f.write(page("証券会社の手数料比較", hikaku,
                     "米国株手数料を実測データつきで比較。手数料差が年率リターンに与える影響を15年バックテストで検証しました。"))

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
    tlist = ("<h1>計算ツール</h1>"
             "<div class='card'><a href='/tools/fukuri.html'>複利計算機</a></div>"
             "<div class='card'><a href='/tools/position-size.html'>ポジションサイズ計算機</a></div>"
             "<div class='card'><a href='/tools/jpy-return.html'>外貨投資の円建てリターン計算機</a></div>")
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
            f"{BASE_URL}/hikaku.html", f"{BASE_URL}/about.html",
            f"{BASE_URL}/tools/fukuri.html", f"{BASE_URL}/tools/position-size.html",
            f"{BASE_URL}/tools/jpy-return.html"] + \
           [f"{BASE_URL}/posts/{p['slug']}.html" for p in posts]
    with open(os.path.join(DOCS, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write("<?xml version='1.0' encoding='UTF-8'?>"
                "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
                + "".join(f"<url><loc>{u}</loc></url>" for u in urls) + "</urlset>")
    with open(os.path.join(DOCS, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n")
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
