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

// for numeric/range assertions, where `cond` is already a boolean
function checkBool(name, cond, detail) {
  if (!cond) fails++;
  console.log(`${cond ? "PASS" : "FAIL"}  ${name}\n      ${detail}`);
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

// ---------------- NISA ----------------
{
  const code = extract("docs/tools/nisa.html");
  const run = (o, out) => {
    const dom = stubDom();
    const set = Object.entries(o).map(([k, v]) =>
      `document.getElementById('${k}').value='${v}';`).join("");
    return new Function("document",
      `${code}\n;${set}calc();return document.getElementById('${out}').innerHTML;`)(dom.document);
  };
  // 50,000/mo for 25y at 5%: principal 15,000,000; FV ~29.8M; gain ~14.8M;
  // tax at 20.315% ~3.0M
  const out = run({ m: 50000, r: 5, y: 25 }, "out");
  check("NISA principal is 15,000,000", out, "15,000,000");
  const m = out.match(/差額<\/div><div class='v'>([\d,]+)円/);
  const diff = m ? Number(m[1].replace(/,/g, "")) : 0;
  checkBool("NISA tax saved is ~3.0M (2.8-3.2M)", diff > 2800000 && diff < 3200000, `got ${diff.toLocaleString()} yen`);
  // zero return -> zero tax saved
  const z = run({ m: 10000, r: 0, y: 10 }, "out");
  check("NISA with 0% return saves 0", z, "差額</div><div class='v'>0円");
}

// ---------------- iDeCo ----------------
{
  const code = extract("docs/tools/ideco.html");
  const run = (o, out) => {
    const dom = stubDom();
    const set = Object.entries(o).map(([k, v]) =>
      `document.getElementById('${k}').value='${v}';`).join("");
    return new Function("document",
      `${code}\n;${set}calc();return document.getElementById('${out}').innerHTML;`)(dom.document);
  };
  // taxable income 3,000,000 -> income-tax bracket 10%; 23,000/mo = 276,000/yr
  // saving = 276,000 * (0.10*1.021 + 0.10) = 276,000 * 0.2021 = 55,780
  const a = run({ m: 23000, t: 3000000, y: 20 }, "out");
  check("iDeCo bracket at taxable 3.0M is 10%", a, "10%");
  check("iDeCo yearly saving ~55,780", a, "55,780");
  // bracket boundary: 1,950,000 stays 5%, 1,950,001 becomes 10%
  check("iDeCo boundary 1,950,000 -> 5%", run({ m: 20000, t: 1950000, y: 1 }, "out"), ">5%<");
  check("iDeCo boundary 1,950,001 -> 10%", run({ m: 20000, t: 1950001, y: 1 }, "out"), ">10%<");
  // 6,950,000 -> 20%, 6,950,001 -> 23%
  check("iDeCo boundary 6,950,000 -> 20%", run({ m: 20000, t: 6950000, y: 1 }, "out"), ">20%<");
  check("iDeCo boundary 6,950,001 -> 23%", run({ m: 20000, t: 6950001, y: 1 }, "out"), ">23%<");
}

// ---------------- furusato ----------------
{
  const code = extract("docs/tools/furusato.html");
  const run = (o, fn, out) => {
    const dom = stubDom();
    const set = Object.entries(o).map(([k, v]) =>
      `document.getElementById('${k}').value='${v}';`).join("");
    return new Function("document",
      `${code}\n;${set}${fn}();return document.getElementById('${out}').textContent;`)(dom.document);
  };
  // Method 1 against the published formula:
  // wari 200,000, taxable 3,000,000 (10% bracket)
  // 200000*0.2/(0.9-0.10*1.021)+2000 = 40000/0.7979+2000 = 52,138 -> 52,000
  check("furusato from wari 200k @10% is 52,000",
    run({ w: 200000, t2: 3000000 }, "calc1", "r1"), "52,000");
  // 総務省の目安: salary 6,000,000 single/dual-income -> about 77,000 yen
  const g = run({ inc: 6000000, fam: 1 }, "calc2", "r2");
  const gm = g.match(/約([\d,]+)円/);
  const got = gm ? Number(gm[1].replace(/,/g, "")) : 0;
  checkBool("furusato estimate for 6M salary within 15% of the 77,000 guideline",
    Math.abs(got - 77000) / 77000 < 0.15, `got ${got.toLocaleString()} vs guideline 77,000`);
  // higher salary must give a higher limit (monotonic)
  const hi = run({ inc: 10000000, fam: 1 }, "calc2", "r2");
  const him = Number((hi.match(/約([\d,]+)円/) || [0, "0"])[1].replace(/,/g, ""));
  checkBool("furusato is monotonic in salary", him > got, `10M -> ${him.toLocaleString()} vs 6M -> ${got.toLocaleString()}`);
}

console.log(fails === 0 ? "\nALL TOOL LOGIC TESTS PASS" : `\n${fails} FAILURES`);
process.exit(fails === 0 ? 0 : 1);
