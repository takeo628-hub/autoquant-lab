// Verify the shipped tool logic by extracting the real <script> from the
// generated HTML and running it against known-answer cases.
const fs = require("fs");

function extract(file) {
  const h = fs.readFileSync(file, "utf8");
  const m = [...h.matchAll(/<script>([\s\S]*?)<\/script>/g)]
    .map(x => x[1])
    .filter(s => !s.includes("v.json"));   // drop the cache-checker script
  return m[m.length - 1];
}

function stubDom(values = {}) {
  const store = {};
  const el = (id) => (store[id] = store[id] || {
    value: values[id] !== undefined ? values[id] : "",
    textContent: "", innerHTML: "", style: {}, dataset: {},
    addEventListener() {}, files: [],
  });
  return {
    document: {
      getElementById: el,
      createElement: () => ({ getContext: () => ({ drawImage() {} }), toBlob() {}, style: {} }),
    },
    get: el,
  };
}

let fails = 0;
function check(name, got, want) {
  const ok = String(got).includes(want);
  if (!ok) fails++;
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}\n      got: ${got}\n      want contains: ${want}`);
}

// ---------------- wareki ----------------
{
  const code = extract("docs/tools/wareki.html");
  const cases = [
    ["1995-04-10", "平成7年4月10日"],
    ["2019-05-01", "令和元年5月1日"],
    ["2019-04-30", "平成31年4月30日"],
    ["1989-01-08", "平成元年1月8日"],
    ["1989-01-07", "昭和64年1月7日"],
    ["1926-12-25", "昭和元年12月25日"],
    ["1912-07-29", "明治45年7月29日"],
  ];
  for (const [input, want] of cases) {
    const dom = stubDom({ d: input, era: "令和", y: "7", m: "4", dd: "10" });
    const fn = new Function("document", code + "\n;return document.getElementById('o1').textContent;");
    check(`wareki ${input}`, fn(dom.document), want);
  }
  // 和暦→西暦
  const dom = stubDom({ d: "1995-04-10", era: "昭和", y: "50", m: "6", dd: "1" });
  const fn = new Function("document", extract("docs/tools/wareki.html") +
    "\n;return document.getElementById('o3').textContent;");
  check("wareki reverse 昭和50年6月1日", fn(dom.document), "1975年6月1日");
}

// ---------------- date-calc ----------------
// NOTE: the tool initialises its date inputs to today on load, so the test
// must set the inputs AFTER running the script, then invoke the function.
{
  const code = extract("docs/tools/date-calc.html");
  const run = (setup, call, out) => {
    const dom = stubDom();
    const fn = new Function("document",
      `${code}\n;${setup}\n${call}\nreturn document.getElementById('${out}').textContent;`);
    return fn(dom.document);
  };
  const set = (o) => Object.entries(o)
    .map(([k, v]) => `document.getElementById('${k}').value='${v}';`).join("");

  // +1 business day from Fri 2026-01-09: Mon 1/12 is 成人の日 -> Tue 1/13
  check("biz +1 from 2026-01-09 (Mon 1/12 is a holiday)",
    run(set({ b: "2026-01-09", n: "1", mode: "biz" }), "addDays();", "r1"), "2026-01-13");
  // calendar +30
  check("cal +30 from 2026-08-06",
    run(set({ b: "2026-08-06", n: "30", mode: "cal" }), "addDays();", "r1"), "2026-09-05");
  // negative business days
  check("biz -1 from 2026-01-13",
    run(set({ b: "2026-01-13", n: "-1", mode: "biz" }), "addDays();", "r1"), "2026-01-09");
  // Golden Week 2026: +1 biz day from Wed 2026-04-29 (昭和の日) -> Thu 4/30
  check("biz +1 from 2026-04-29 (holiday itself)",
    run(set({ b: "2026-04-29", n: "1", mode: "biz" }), "addDays();", "r1"), "2026-04-30");
  // between: Jan 1..Jan 31 = 30 days
  check("between 2026-01-01..01-31 days",
    run(set({ s: "2026-01-01", e: "2026-01-31" }), "between();", "r2"), "30日間");
  // between: business days in that span (Jan 12 holiday excluded)
  check("between 2026-01-01..01-31 biz",
    run(set({ s: "2026-01-01", e: "2026-01-31" }), "between();", "r2"), "営業日 20日");
}

// ---------------- moji-count ----------------
{
  const code = extract("docs/tools/moji-count.html");
  const dom = stubDom({ t: "あいうえお かきくけこ\nさしすせそ" });
  const fn = new Function("document", code + "\n;return document.getElementById('out').innerHTML;");
  const out = fn(dom.document);
  check("moji total (17 incl space+newline)", out, ">17<");
  check("moji nospace (15)", out, ">15<");
  check("moji lines (2)", out, ">2<");
}

console.log(fails === 0 ? "\nALL TOOL LOGIC TESTS PASS" : `\n${fails} FAILURES`);
process.exit(fails === 0 ? 0 : 1);
