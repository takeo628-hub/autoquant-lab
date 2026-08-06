// Known-answer tests for the invoice / corporate-number logic BEFORE it ships.
// Money and tax numbers are the one place a plausible-looking wrong answer does
// real damage, so every rule here is pinned to a value I can justify.

// ---- corporate number check digit (National Tax Agency algorithm) ----------
// check = 9 - (sum(Pn * Qn) mod 9), where Pn is the n-th digit from the right
// of the 12-digit base and Qn is 1 for odd n, 2 for even n.
function corporateCheckDigit(base12) {
  if (!/^\d{12}$/.test(base12)) throw new Error("base must be 12 digits");
  let sum = 0;
  for (let n = 1; n <= 12; n++) {
    const digit = Number(base12[12 - n]);
    sum += digit * (n % 2 === 1 ? 1 : 2);
  }
  return 9 - (sum % 9);
}

function validateCorporateNumber(num) {
  const t = String(num).replace(/[\s-]/g, "").replace(/^T/i, "");
  if (!/^\d{13}$/.test(t)) return { valid: false, reason: "13桁の数字ではありません" };
  const expected = corporateCheckDigit(t.slice(1));
  return Number(t[0]) === expected
    ? { valid: true, corporate_number: t, registration_number: "T" + t }
    : { valid: false, reason: `検査用数字が一致しません（期待値 ${expected}）` };
}

// ---- invoice tax: rounding once per tax rate, per invoice ------------------
// Japan's qualified-invoice rules allow rounding the consumption tax ONCE per
// tax rate for the whole invoice. Rounding each line first is not permitted and
// produces a different total, which is the bug most free tools ship.
// Integer numerator/denominator per rate. Dividing by (1 + rate) in floating
// point put a tax-included 1,100 yen line at 999.9999999999999, which floored
// to 999 and lost a yen off the subtotal — so the tax is derived with exact
// integer arithmetic and net is back-solved to keep net + tax == gross.
const RATE_MATH = {
  0.1: { excl: [10, 100], incl: [10, 110] },
  0.08: { excl: [8, 100], incl: [8, 108] },
};

function invoiceTotals(lines, { roundMode = "floor", taxIncluded = false } = {}) {
  const round = (x) => (roundMode === "ceil" ? Math.ceil(x)
    : roundMode === "round" ? Math.round(x) : Math.floor(x));
  const byRate = new Map();
  for (const l of lines) {
    const rate = Number(l.rate);
    if (!RATE_MATH[rate]) throw new Error(`unsupported rate: ${l.rate}`);
    byRate.set(rate, (byRate.get(rate) ?? 0) + Number(l.qty) * Number(l.unitPrice));
  }
  const groups = [...byRate.entries()]
    .sort((a, b) => b[0] - a[0])
    .map(([rate, raw]) => {
      const amount = Math.round(raw);          // to whole yen first
      if (taxIncluded) {
        const [num, den] = RATE_MATH[rate].incl;
        const tax = round((amount * num) / den);   // rounded once per rate
        return { rate, net: amount - tax, tax, gross: amount };
      }
      const [num, den] = RATE_MATH[rate].excl;
      const tax = round((amount * num) / den);     // rounded once per rate
      return { rate, net: amount, tax, gross: amount + tax };
    });
  return {
    groups,
    subtotal: groups.reduce((s, g) => s + g.net, 0),
    tax_total: groups.reduce((s, g) => s + g.tax, 0),
    total: groups.reduce((s, g) => s + g.gross, 0),
  };
}

// the wrong way, kept only to prove the two differ
function perLineRounding(lines) {
  return lines.reduce((s, l) =>
    s + Math.floor(Number(l.qty) * Number(l.unitPrice) * Number(l.rate)), 0);
}

let fails = 0;
const eq = (name, got, want) => {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) fails++;
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}`
    + (ok ? "" : `\n      got  ${JSON.stringify(got)}\n      want ${JSON.stringify(want)}`));
};
const truthy = (name, cond, detail = "") => {
  if (!cond) fails++;
  console.log(`${cond ? "PASS" : "FAIL"}  ${name}${detail ? `\n      ${detail}` : ""}`);
};

// --- corporate numbers ----------------------------------------------------
// Two real numbers, verified by hand against the published algorithm.
eq("Toyota 1180301018771 validates", validateCorporateNumber("1180301018771").valid, true);
eq("NTA 7000012050002 validates", validateCorporateNumber("7000012050002").valid, true);
eq("T-prefixed input is accepted",
  validateCorporateNumber("T1180301018771").valid, true);
eq("hyphens are tolerated",
  validateCorporateNumber("1180-3010-18771").valid, true);
eq("a single altered digit is rejected",
  validateCorporateNumber("1180301018772").valid, false);
eq("a wrong check digit is rejected",
  validateCorporateNumber("2180301018771").valid, false);
eq("12 digits is rejected", validateCorporateNumber("118030101877").valid, false);
eq("non-numeric is rejected", validateCorporateNumber("T118030101877X").valid, false);
eq("valid input returns the T-prefixed registration number",
  validateCorporateNumber("1180301018771").registration_number, "T1180301018771");

// --- rounding once per rate ------------------------------------------------
// 3 lines at 10%: 1,001 / 2,003 / 3,007 -> net 6,011, tax floor(601.1) = 601.
// Rounding each line first gives 100 + 200 + 300 = 600, which is 1 yen short.
const lines10 = [
  { qty: 1, unitPrice: 1001, rate: 0.1 },
  { qty: 1, unitPrice: 2003, rate: 0.1 },
  { qty: 1, unitPrice: 3007, rate: 0.1 },
];
const t10 = invoiceTotals(lines10);
eq("subtotal is the sum of the lines", t10.subtotal, 6011);
eq("tax is rounded once for the rate group", t10.tax_total, 601);
eq("per-line rounding gives a different (non-compliant) figure",
  perLineRounding(lines10), 600);
truthy("the two methods really do differ",
  t10.tax_total !== perLineRounding(lines10),
  `once-per-rate ${t10.tax_total} vs per-line ${perLineRounding(lines10)}`);

// mixed rates are grouped separately, each rounded once
const mixed = [
  { qty: 3, unitPrice: 333, rate: 0.1 },    // net 999  -> tax floor(99.9)  = 99
  { qty: 3, unitPrice: 111, rate: 0.08 },   // net 333  -> tax floor(26.64) = 26
];
const tm = invoiceTotals(mixed);
eq("two rate groups are produced", tm.groups.length, 2);
eq("10% group: net 999, tax 99", [tm.groups[0].net, tm.groups[0].tax], [999, 99]);
eq("8% group: net 333, tax 26", [tm.groups[1].net, tm.groups[1].tax], [333, 26]);
eq("grand total adds the groups", tm.total, 999 + 99 + 333 + 26);

// rounding modes
eq("floor mode", invoiceTotals([{ qty: 1, unitPrice: 999, rate: 0.1 }],
  { roundMode: "floor" }).tax_total, 99);
eq("ceil mode", invoiceTotals([{ qty: 1, unitPrice: 999, rate: 0.1 }],
  { roundMode: "ceil" }).tax_total, 100);
eq("round mode", invoiceTotals([{ qty: 1, unitPrice: 995, rate: 0.1 }],
  { roundMode: "round" }).tax_total, 100);   // 99.5 -> 100

// tax-included input is converted back to net before grouping
const inc = invoiceTotals([{ qty: 1, unitPrice: 1100, rate: 0.1 }],
  { taxIncluded: true });
eq("tax-included 1,100 at 10% -> net 1,000 / tax 100",
  [inc.subtotal, inc.tax_total, inc.total], [1000, 100, 1100]);

// unsupported rate must fail loudly rather than guess
try {
  invoiceTotals([{ qty: 1, unitPrice: 100, rate: 0.05 }]);
  truthy("an unsupported tax rate is rejected", false, "no error thrown");
} catch {
  truthy("an unsupported tax rate is rejected", true);
}

console.log(fails === 0 ? "\nALL INVOICE LOGIC TESTS PASS" : `\n${fails} FAILURES`);
process.exit(fails === 0 ? 0 : 1);
