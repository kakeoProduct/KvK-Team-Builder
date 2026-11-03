"use strict";
// 集結タイムライン計算（web/攻城タイムライン計算.html）を実物のまま動かす検査。
// 要件IDと性質はdocs/requirements/web-tools/siege-timeline.mdを参照する。
// 期待値は要件の式から手で求めた値であり、実装の出力を書き写したものではない。

const test = require("node:test");
const assert = require("node:assert/strict");
const {
  DEFAULT_PET_BONUS, createClock, openSiege, storageOf, readJson, setValue, setChecked, $, $$,
  fillSiege, calculate, createRandom, randomSiegeCase, STORAGE_FAILURES,
} = require("./helpers");
const { checkProperties, toSeconds } = require("./siege-properties");
const { CASES, SHARDS, shardCases } = require("./siege-random");

// 例1: 削りの集結5分、メイン／増援の集結3分、フェーズ間隔1秒、バッファ30秒。
// Bは速度ペットLv8（+30%）を採用し、行軍は100 ÷ 1.3 = 76.9…を四捨五入した77秒（SIEGE-019）。
const EXAMPLE1 = {
  settings: { kz: 5, mr: 3, gap: 1, buf: 30 },
  petSame: null,
  members: [
    { role: "メイン", label: "M", march: 60 },
    { role: "増援", label: "R", march: 40 },
    { role: "削り", label: "A", march: 30 },
    { role: "削り", label: "B", march: 100, pet: 8, usePet: true },
    { role: "削り", label: "C", march: 50 },
  ],
  patterns: [
    { kezuri: ["A", "B"], reinforce: ["R"] },
    { kezuri: ["C"], reinforce: [] },
  ],
};
// 1周目①: T = max(0, A 0+300+30, B 0+300+77, M 0+180+60-1, R 0+180+40-2) = 377。
//   使用可能時刻は A 407+30、B 454+30、M 438+30、R 419+30 になる。
// 1周目②: T = max(0, C 0+300+50, M 468+180+60-1) = 707。C 757+30、M 768+30。
// 2周目①: T = max(A 437+330, B 484+377, M 798+239, R 449+218) = 1037。
// 2周目②: T = max(C 787+350, M 1128+239) = 1367。周期は1037 - 377 = 660秒（SIEGE-017）。
const EXAMPLE1_ROUND1 = [
  "①A+B→メイン→増援",
  "0分00秒 → ①B（5分集結）※行軍77秒（6分17秒着、7分34秒帰還）",
  "0分47秒 → ①A（5分集結）※行軍30秒（6分17秒着、6分47秒帰還）",
  "2分18秒 → ①M（3分集結）※行軍60秒（6分18秒着、7分18秒帰還）",
  "2分39秒 → ①R（3分集結）※行軍40秒（6分19秒着、6分59秒帰還）",
  "",
  "②C→メイン",
  "5分57秒 → ②C（5分集結）※行軍50秒（11分47秒着、12分37秒帰還）",
  "7分48秒 → ②M（3分集結）※行軍60秒（11分48秒着、12分48秒帰還）",
].join("\n");
const EXAMPLE1_ROUND2 = [
  "①A+B→メイン→増援",
  "11分00秒 → ①B（5分集結）※行軍77秒（17分17秒着、18分34秒帰還）",
  "11分47秒 → ①A（5分集結）※行軍30秒（17分17秒着、17分47秒帰還）",
  "13分18秒 → ①M（3分集結）※行軍60秒（17分18秒着、18分18秒帰還）",
  "13分39秒 → ①R（3分集結）※行軍40秒（17分19秒着、17分59秒帰還）",
  "",
  "②C→メイン",
  "16分57秒 → ②C（5分集結）※行軍50秒（22分47秒着、23分37秒帰還）",
  "18分48秒 → ②M（3分集結）※行軍60秒（22分48秒着、23分48秒帰還）",
].join("\n");
const EXAMPLE1_OUTPUT = `${EXAMPLE1_ROUND1}\n\n周期：11分00秒`;
const EXAMPLE1_REFERENCE = `【1周目】\n${EXAMPLE1_ROUND1}\n\n【2周目】\n${EXAMPLE1_ROUND2}\n\n周期：11分00秒`;

const SAMPLE_MEMBERS = [
  ["メイン", "メイン"], ["増援", "増援"],
  ["削り", "A"], ["削り", "B"], ["削り", "C"], ["削り", "D"], ["削り", "E"], ["削り", "F"],
];

function memberRows(dom) {
  return $$(dom, "#memberBody tr").map(row => [
    row.querySelector(".role-select").value, row.querySelector(".label-input").value,
  ]);
}

// パターンごとに、名前と、選んだ削りと増援のラベルを返す。
function patternSelections(dom) {
  return $$(dom, ".pattern-block").map(block => {
    const checked = type => Array.from(block.querySelectorAll(`input[data-type="${type}"]:checked`))
      .map(box => box.parentElement.textContent.trim());
    return [block.querySelector(".pattern-name-input").value, checked("kezuri"), checked("reinforce")];
  });
}

function open(t, options) {
  const dom = openSiege(options);
  t.after(() => dom.window.close());
  return dom;
}

function rowOf(dom, label) {
  return $$(dom, "#memberBody tr").find(row => row.querySelector(".label-input").value === label);
}

// 出力のうち、指定したパターンの行の時刻をすべてdelta秒ずらす（性質の検査の検出力を確かめる）。
function shiftPattern(text, name, delta) {
  const format = sec => `${Math.floor(sec / 60)}分${String(sec % 60).padStart(2, "0")}秒`;
  return text.split("\n").map(line => line.includes(` → ${name}`)
    ? line.replace(/(\d+)分(\d{2})秒/g, time => format(toSeconds(time) + delta))
    : line).join("\n");
}

test.describe("計算規則と出力（SIEGE-010〜SIEGE-025、性質C1〜C3、C8〜C12）", () => {
  test("例1: 定義順に確定し、手で求めた1周目、2周目、周期を出力する", t => {
    const dom = open(t);
    fillSiege(dom, EXAMPLE1);
    // 速度ペットありの行軍秒数を、四捨五入して表示する（SIEGE-007）。
    assert.equal(rowOf(dom, "B").querySelector(".march-pet-output").value, "77");
    assert.equal(rowOf(dom, "A").querySelector(".march-pet-output").value, "（ペットなし）");
    const { output, reference } = calculate(dom);
    assert.equal(output, EXAMPLE1_OUTPUT);
    assert.equal(reference, EXAMPLE1_REFERENCE);
    assert.equal($(dom, "#outputCard").style.display, "block");
    assert.equal($(dom, "#refOutputCard").style.display, "block");
    assert.deepEqual(checkProperties(EXAMPLE1, output, reference), []);
  });

  test("例1で採用をオフにすると、速度ペットがあってもペットなしの行軍秒数を使う（SIEGE-019）", t => {
    const dom = open(t);
    fillSiege(dom, { ...EXAMPLE1, members: EXAMPLE1.members.map(m => m.label === "B" ? { ...m, usePet: false } : m) });
    const { output } = calculate(dom);
    // ①のTは B 0+300+100 = 400 になり、Bは0秒に発起して8分20秒に着く。
    assert.match(output, /^①A\+B→メイン→増援\n0分00秒 → ①B（5分集結）※行軍100秒（6分40秒着、8分20秒帰還）\n/);
  });

  test("例2: メインが0人なら、削りだけのパターンは独立に進み、2周目のブロックは発起の早い順に並ぶ（SIEGE-018、SIEGE-024、SIEGE-025）", t => {
    // メインが0人でもメッセージを出さずに計算する（SIEGE-018）。出力の全文を比べるため、メッセージがないことも確かめる。
    const testCase = {
      settings: { kz: 5, mr: 3, gap: 1, buf: 0 },
      petSame: null,
      members: [{ role: "削り", label: "A", march: 1000 }, { role: "削り", label: "D", march: 0 }],
      patterns: [{ kezuri: ["A"], reinforce: [] }, { kezuri: ["D"], reinforce: [] }, { kezuri: [], reinforce: [] }],
    };
    const dom = open(t);
    fillSiege(dom, testCase);
    const { output, reference } = calculate(dom);
    // 1周目: ① T=1300、② T=300。どちらも0秒に発起するため定義順。③は行がないため出さない。
    // 2周目: ① T=2300+1300=3600、② T=300+300=600。②が先に発起する。60分以上も時間へ繰り上げない（SIEGE-022）。
    const round1 = [
      "①A→メイン",
      "0分00秒 → ①A（5分集結）※行軍1000秒（21分40秒着、38分20秒帰還）",
      "",
      "②D→メイン",
      "0分00秒 → ②D（5分集結）※行軍0秒（5分00秒着、5分00秒帰還）",
    ].join("\n");
    const round2 = [
      "②D→メイン",
      "5分00秒 → ②D（5分集結）※行軍0秒（10分00秒着、10分00秒帰還）",
      "",
      "①A→メイン",
      "38分20秒 → ①A（5分集結）※行軍1000秒（60分00秒着、76分40秒帰還）",
    ].join("\n");
    assert.equal(output, `${round1}\n\n周期：38分20秒`);
    assert.equal(reference, `【1周目】\n${round1}\n\n【2周目】\n${round2}\n\n周期：38分20秒`);
    assert.deepEqual(checkProperties(testCase, output, reference), []);
  });

  test("例3: 同じ発起の行は、メンバーの並びによらず削り、メイン、増援の順に並ぶ（SIEGE-024）", t => {
    const testCase = {
      settings: { kz: 3, mr: 3, gap: 0, buf: 0 },
      petSame: null,
      members: [
        { role: "増援", label: "R", march: 0 },
        { role: "メイン", label: "M", march: 0 },
        { role: "削り", label: "A", march: 0 },
      ],
      patterns: [{ kezuri: ["A"], reinforce: ["R"] }],
    };
    const dom = open(t);
    fillSiege(dom, testCase);
    const { output, reference } = calculate(dom);
    assert.equal(output, [
      "①A→メイン→増援",
      "0分00秒 → ①A（3分集結）※行軍0秒（3分00秒着、3分00秒帰還）",
      "0分00秒 → ①M（3分集結）※行軍0秒（3分00秒着、3分00秒帰還）",
      "0分00秒 → ①R（3分集結）※行軍0秒（3分00秒着、3分00秒帰還）",
      "",
      "周期：3分00秒",
    ].join("\n"));
    assert.deepEqual(checkProperties(testCase, output, reference), []);
  });

  test("例4: 選んだ順によらず、見出しの削りと、同じ発起で同じ役割の行は、メンバー表の順に並ぶ（SIEGE-024）", t => {
    const testCase = {
      settings: { kz: 3, mr: 3, gap: 0, buf: 0 },
      petSame: null,
      members: [
        { role: "削り", label: "K2", march: 10 },
        { role: "削り", label: "K0", march: 10 },
        { role: "削り", label: "K1", march: 10 },
        { role: "メイン", label: "M", march: 0 },
      ],
      // fillSiegeはこの順（メンバー表と違う順）にクリックする。
      patterns: [{ kezuri: ["K1", "K0", "K2"], reinforce: [] }],
    };
    const dom = open(t);
    fillSiege(dom, testCase);
    const { output, reference } = calculate(dom);
    // T = max(0, 削り 0+180+10, M 0+180+0-0) = 190。削りは0秒に発起し190秒に着いて200秒に帰還する。
    // 2周目: T = max(削り 200+190, M 190+180) = 390。周期は390 - 190 = 200秒（SIEGE-017）。
    const round1 = [
      "①K2+K0+K1→メイン",
      "0分00秒 → ①K2（3分集結）※行軍10秒（3分10秒着、3分20秒帰還）",
      "0分00秒 → ①K0（3分集結）※行軍10秒（3分10秒着、3分20秒帰還）",
      "0分00秒 → ①K1（3分集結）※行軍10秒（3分10秒着、3分20秒帰還）",
      "0分10秒 → ①M（3分集結）※行軍0秒（3分10秒着、3分10秒帰還）",
    ].join("\n");
    assert.equal(output, `${round1}\n\n周期：3分20秒`);
    assert.deepEqual(checkProperties(testCase, output, reference), []);
    // 見出しのラベルと、同じ発起の削りの行を入れ替えると、性質の検査がSIEGE-024として検出する。
    const names = violations => [...new Set(violations.map(v => v.split(":")[0]))].sort();
    const swapHeader = text => text.replaceAll("①K2+K0+K1", "①K0+K2+K1");
    assert.deepEqual(names(checkProperties(testCase, swapHeader(output), swapHeader(reference))), ["SIEGE-024"]);
    const swapLines = text => text.replaceAll("→ ①K2（", "→ ①TMP（").replaceAll("→ ①K0（", "→ ①K2（").replaceAll("→ ①TMP（", "→ ①K0（");
    assert.deepEqual(names(checkProperties(testCase, swapLines(output), swapLines(reference))), ["SIEGE-024"]);
  });

  test("メインが0人で増援だけを選んだパターンは、増援の着弾からTを決める（SIEGE-012、SIEGE-014、SIEGE-018）", t => {
    const testCase = {
      settings: { kz: 3, mr: 3, gap: 1, buf: 0 },
      petSame: null,
      members: [{ role: "削り", label: "K", march: 20 }, { role: "増援", label: "R", march: 10 }],
      patterns: [{ kezuri: [], reinforce: ["R"] }, { kezuri: ["K"], reinforce: [] }],
    };
    const dom = open(t);
    fillSiege(dom, testCase);
    const { output, reference } = calculate(dom);
    // ①: T = max(0, R 0+180+10-2) = 188。Rは190秒に着き200秒に帰還する。
    // ②: T = max(0, K 0+180+20) = 200。2周目①: T = 200+188 = 388。周期は388 - 188 = 200秒。
    assert.equal(output, [
      "①→メイン→増援",
      "0分00秒 → ①R（3分集結）※行軍10秒（3分10秒着、3分20秒帰還）",
      "",
      "②K→メイン",
      "0分00秒 → ②K（3分集結）※行軍20秒（3分20秒着、3分40秒帰還）",
      "",
      "周期：3分20秒",
    ].join("\n"));
    assert.deepEqual(checkProperties(testCase, output, reference), []);
  });

  test("削りを選ばないパターンは、メインと増援で着弾を決める（SIEGE-012、SIEGE-018）", t => {
    const testCase = {
      settings: { kz: 5, mr: 3, gap: 2, buf: 10 },
      petSame: null,
      members: [{ role: "メイン", label: "M", march: 20 }, { role: "増援", label: "R", march: 50 }, { role: "削り", label: "A", march: 10 }],
      patterns: [{ kezuri: [], reinforce: ["R"] }, { kezuri: ["A"], reinforce: [] }],
    };
    const dom = open(t);
    fillSiege(dom, testCase);
    const { output, reference } = calculate(dom);
    // ①: T = max(0, M 0+180+20-2, R 0+180+50-4) = 226。Rは0秒に発起し、228秒にMが、230秒にRが着く。
    assert.match(output, /^①→メイン→増援\n0分00秒 → ①R（3分集結）※行軍50秒（3分50秒着、4分40秒帰還）\n/);
    assert.deepEqual(checkProperties(testCase, output, reference), []);
  });

  test("パターンが0件なら時刻を計算せずに知らせ、参考の結果と周期ウェーブタイマーへ渡す結果は変えない（SIEGE-032）", t => {
    const dom = open(t);
    fillSiege(dom, EXAMPLE1);
    calculate(dom);
    const saved = dom.window.localStorage.getItem("siegeTimelineForWaveTimer");
    while ($$(dom, ".del-pattern-btn").length) $(dom, ".del-pattern-btn").click();
    assert.equal($(dom, "#patternList .empty").textContent, "パターンがありません");
    const { output, reference } = calculate(dom);
    assert.equal(output, "パターンが設定されていません。");
    assert.equal(reference, EXAMPLE1_REFERENCE);
    assert.equal(dom.window.localStorage.getItem("siegeTimelineForWaveTimer"), saved);
  });

  test("初めての計算でパターンが0件なら、参考の結果を出さず、渡す結果も保存しない（SIEGE-032）", t => {
    const dom = open(t);
    while ($$(dom, ".del-pattern-btn").length) $(dom, ".del-pattern-btn").click();
    const { output, reference } = calculate(dom);
    assert.equal(output, "パターンが設定されていません。");
    assert.equal(reference, "");
    assert.equal($(dom, "#refOutputCard").style.display, "none");
    assert.equal(dom.window.localStorage.getItem("siegeTimelineForWaveTimer"), null);
  });

  test("決定的な乱数（種7）の100件を、ボーナスの既定値のまま1つのページで続けて計算しても性質を満たす（削りを選ばないパターンを含む）", t => {
    const rnd = createRandom(7);
    const dom = open(t);
    const failures = [];
    for (let i = 0; i < 100; i++) {
      const testCase = randomSiegeCase(rnd);
      fillSiege(dom, testCase);
      const { output, reference } = calculate(dom);
      const violations = checkProperties(testCase, output, reference, { saved: readJson(dom, "siegeTimelineForWaveTimer") });
      if (violations.length) failures.push({ i, violations });
    }
    assert.deepEqual(failures.slice(0, 3), []);
  });
});

test.describe("性質の検査が違反を検出する", () => {
  const check = (output, reference, options) => checkProperties(EXAMPLE1, output, reference, options);
  const names = violations => [...new Set(violations.map(v => v.split(":")[0]))].sort();

  test("手で求めた例1の出力は、どの性質にも違反しない", () => {
    assert.deepEqual(check(EXAMPLE1_OUTPUT, EXAMPLE1_REFERENCE), []);
  });

  test("着弾、発起、帰還のずれをC3で検出する", () => {
    const wrong = text => text.replace("0分47秒 → ①A", "0分48秒 → ①A");
    assert.ok(names(check(wrong(EXAMPLE1_OUTPUT), wrong(EXAMPLE1_REFERENCE))).includes("C3"));
  });

  test("必要以上に遅い着弾をC10で、待ち時間の違反をC2で検出する", () => {
    // 最後に確定する2周目の②を10秒遅らせても、待ち時間と階段状の着弾は守られる。
    const late = EXAMPLE1_REFERENCE.replace(EXAMPLE1_ROUND2, shiftPattern(EXAMPLE1_ROUND2, "②", 10));
    assert.deepEqual(names(check(EXAMPLE1_OUTPUT, late)), ["C10"]);
    // 1周目の②を100秒早めると、メインが①から戻る前に発起する。
    const early = text => text.replace(EXAMPLE1_ROUND1, shiftPattern(EXAMPLE1_ROUND1, "②", -100));
    const found = names(check(early(EXAMPLE1_OUTPUT), early(EXAMPLE1_REFERENCE)));
    assert.ok(found.includes("C2") && found.includes("C10"), found.join(","));
  });

  test("周期の誤りをC11で、1周目の出力と参考の不一致をC8で検出する", () => {
    const cycle = text => text.replace("周期：11分00秒", "周期：11分01秒");
    assert.deepEqual(names(check(cycle(EXAMPLE1_OUTPUT), cycle(EXAMPLE1_REFERENCE))), ["C11"]);
    // 性質C1〜C3、C9〜C12は参考の結果から判定するため、1周目の出力だけを変える。
    assert.deepEqual(names(check(EXAMPLE1_OUTPUT.replace("7分48秒 → ②M", "7分49秒 → ②M"), EXAMPLE1_REFERENCE)), ["C8"]);
  });

  test("行軍の誤りをC12で、負の時刻をC1で、行の欠落と見出しの誤りをC9で検出する", () => {
    const table = DEFAULT_PET_BONUS.map((v, i) => (i === 8 ? 40 : v));
    assert.ok(names(check(EXAMPLE1_OUTPUT, EXAMPLE1_REFERENCE, { bonusTable: table })).includes("C12"));
    const negative = text => text.replace("0分00秒 → ①B", "-1分00秒 → ①B");
    assert.deepEqual(names(check(negative(EXAMPLE1_OUTPUT), negative(EXAMPLE1_REFERENCE))), ["C1"]);
    const missing = text => text.replace(/\n0分47秒 → ①A.*/, "");
    assert.deepEqual(names(check(missing(EXAMPLE1_OUTPUT), missing(EXAMPLE1_REFERENCE))), ["C9"]);
    const header = text => text.replace("②C→メイン", "②C→メイン→増援");
    assert.deepEqual(names(check(header(EXAMPLE1_OUTPUT), header(EXAMPLE1_REFERENCE))), ["C9"]);
  });

  test("行とブロックの並びの誤りをSIEGE-024、SIEGE-025で検出する", () => {
    const lines = EXAMPLE1_ROUND1.split("\n");
    const swapLines = [lines[0], lines[2], lines[1], ...lines.slice(3)].join("\n");
    const swapBlocks = [...lines.slice(6), "", ...lines.slice(0, 5)].join("\n");
    const replace = (from, to) => [
      EXAMPLE1_OUTPUT.replace(from, to), EXAMPLE1_REFERENCE.replace(from, to),
    ];
    assert.deepEqual(names(check(...replace(EXAMPLE1_ROUND1, swapLines))), ["SIEGE-024"]);
    assert.deepEqual(names(check(...replace(EXAMPLE1_ROUND1, swapBlocks))), ["SIEGE-025"]);
  });

  test("周期ウェーブタイマーへ渡す結果の誤りをSIEGE-045で検出する", () => {
    const saved = { periodSec: 660, maxSec: 768, rawText: EXAMPLE1_OUTPUT };
    assert.deepEqual(check(EXAMPLE1_OUTPUT, EXAMPLE1_REFERENCE, { saved }), []);
    for (const wrong of [{ periodSec: 661 }, { maxSec: 757 }, { rawText: EXAMPLE1_ROUND1 }]) {
      assert.deepEqual(names(check(EXAMPLE1_OUTPUT, EXAMPLE1_REFERENCE, { saved: { ...saved, ...wrong } })), ["SIEGE-045"]);
    }
  });
});

test.describe("決定的な乱数の入力", () => {
  test(`${CASES}件を${SHARDS}個のファイルで漏れなく重複なく検査する`, () => {
    const indexes = [];
    for (let shard = 1; shard <= SHARDS; shard++) indexes.push(...shardCases(shard).map(c => c.index));
    assert.deepEqual(indexes.sort((a, b) => a - b), Array.from({ length: CASES }, (_, i) => i));
  });

  test("入力は要件の範囲にあり、速度ペットのLv、採用、「全員同じ」、削りなしのパターンを含む", () => {
    const all = [];
    for (let shard = 1; shard <= SHARDS; shard++) all.push(...shardCases(shard).map(c => c.testCase));
    const count = (testCase, role) => testCase.members.filter(m => m.role === role).length;
    for (const testCase of all) {
      assert.ok(count(testCase, "メイン") >= 1 && count(testCase, "メイン") <= 2);
      assert.ok(count(testCase, "増援") <= 2);
      assert.ok(count(testCase, "削り") >= 1 && count(testCase, "削り") <= 8);
      assert.ok(testCase.patterns.length >= 1 && testCase.patterns.length <= 5);
    }
    const some = predicate => all.some(predicate);
    assert.ok(some(c => c.members.some(m => m.pet === 0)));
    for (let lv = 1; lv <= 8; lv++) assert.ok(some(c => c.members.some(m => m.pet === lv)), `Lv${lv}`);
    assert.ok(some(c => c.members.some(m => m.pet && m.usePet === false)));
    assert.ok(some(c => c.petSame === true) && some(c => c.petSame === false));
    assert.ok(some(c => c.patterns.some(p => p.kezuri.length === 0)));
    assert.ok(some(c => c.patterns.some(p => p.reinforce.length === 0) && count(c, "増援") > 0));
  });
});

test.describe("入力（SIEGE-001〜SIEGE-009）", () => {
  test("保存データがなければ、共通設定の既定値とサンプルを表示し、結果カードは出さない（SIEGE-001、SIEGE-006）", t => {
    const dom = open(t);
    assert.deepEqual(["kezuriRallyMin", "mainRallyMin", "phaseGap", "buffer"].map(id => $(dom, "#" + id).value), ["5", "3", "1", "30"]);
    assert.deepEqual(memberRows(dom), SAMPLE_MEMBERS);
    assert.ok($$(dom, ".march-input").every(input => input.value === "0"));
    assert.deepEqual(patternSelections(dom), [
      ["①", ["A", "B", "C"], ["増援"]],
      ["②", ["D"], ["増援"]],
      ["③", ["E", "F"], ["増援"]],
    ]);
    assert.equal($(dom, "#outputCard").style.display, "none");
    assert.equal($(dom, "#refOutputCard").style.display, "none");
  });

  test("保存データのメンバーが0人なら、サンプルを表示する（SIEGE-006）", t => {
    const state = { memberSeq: 0, patternSeq: 0, members: [], patterns: [], settings: { kezuriRallyMin: "4" } };
    const dom = open(t, { storage: { siegeCalcState: JSON.stringify(state) } });
    assert.deepEqual(memberRows(dom), SAMPLE_MEMBERS);
    assert.equal(patternSelections(dom).length, 3);
  });

  test("追加した行は削り、ラベル空、行軍0、速度ペットなし、採用オンで、「全員同じ」がオンならその値に従う（SIEGE-002）", t => {
    const dom = open(t);
    $(dom, "#addMemberBtn").click();
    const row = $$(dom, "#memberBody tr").pop();
    assert.deepEqual(
      [".role-select", ".label-input", ".march-input", ".pet-select"].map(s => row.querySelector(s).value),
      ["削り", "", "0", "0"]);
    assert.equal(row.querySelector(".use-pet-checkbox").checked, true);

    setChecked($(dom, "#petSameAllCheckbox"), true);
    setChecked($(dom, "#petSameValueCheckbox"), false);
    $(dom, "#addMemberBtn").click();
    const added = $$(dom, "#memberBody tr").pop().querySelector(".use-pet-checkbox");
    assert.equal(added.checked, false);
    assert.equal(added.disabled, true);
    // 「削除」で行を削除する。
    $$(dom, ".del-member-btn").pop().click();
    assert.equal($$(dom, "#memberBody tr").length, SAMPLE_MEMBERS.length + 1);
  });

  test("追加したパターンは①〜⑳、21個目から(21)と名付け、その時点の増援を全員選ぶ（SIEGE-003）", t => {
    const dom = open(t);
    $(dom, "#addMemberBtn").click();
    const row = $$(dom, "#memberBody tr").pop();
    setValue(dom, row.querySelector(".label-input"), "増援2");
    setValue(dom, $$(dom, "#memberBody .role-select").pop(), "増援", "change");
    for (let i = 0; i < 18; i++) $(dom, "#addPatternBtn").click();
    const selections = patternSelections(dom);
    assert.deepEqual(selections.map(s => s[0]), [..."①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳", "(21)"]);
    // 既存のパターンには、後から加えた増援を選ばない。
    assert.deepEqual(selections[0].slice(1), [["A", "B", "C"], ["増援"]]);
    assert.deepEqual(selections[3].slice(1), [[], ["増援", "増援2"]]);
  });

  test("メンバーを削除すると、全パターンの削りと増援の選択からも外す（SIEGE-004）", t => {
    const dom = open(t);
    const ids = label => rowOf(dom, label).querySelector(".del-member-btn").dataset.id;
    const removed = [ids("A"), ids("増援")];
    rowOf(dom, "A").querySelector(".del-member-btn").click();
    rowOf(dom, "増援").querySelector(".del-member-btn").click();
    const state = readJson(dom, "siegeCalcState");
    for (const pattern of state.patterns) {
      for (const id of removed) {
        assert.ok(!pattern.kezuriIds.includes(id) && !pattern.reinforceIds.includes(id), JSON.stringify(pattern));
      }
    }
    assert.deepEqual(patternSelections(dom)[0].slice(1), [["B", "C"], []]);
  });

  test("削り、増援、パターンがなければ、その旨を表示する（SIEGE-005）", t => {
    const dom = open(t);
    for (const label of ["A", "B", "C", "D", "E", "F", "増援"]) rowOf(dom, label).querySelector(".del-member-btn").click();
    const block = $(dom, ".pattern-block");
    assert.deepEqual(Array.from(block.querySelectorAll(".kezuri-checks .empty")).map(e => e.textContent),
      ["削り役割のメンバーがいません", "増援役割のメンバーがいません"]);
    while ($$(dom, ".del-pattern-btn").length) $(dom, ".del-pattern-btn").click();
    assert.equal($(dom, "#patternList .empty").textContent, "パターンがありません");
  });

  test("速度ペットLvは持っていない、Lv8…Lv1の順に選び、ペットありの行軍秒数を四捨五入して表示する（SIEGE-007）", t => {
    const dom = open(t);
    const row = rowOf(dom, "A");
    const select = row.querySelector(".pet-select");
    assert.deepEqual(Array.from(select.options).map(o => [o.value, o.textContent]), [
      ["0", "持っていない"],
      ...[8, 7, 6, 5, 4, 3, 2, 1].map(lv => [String(lv), `Lv${lv}（+${DEFAULT_PET_BONUS[lv]}%）`]),
    ]);
    const display = row.querySelector(".march-pet-output");
    assert.equal(display.readOnly, true);
    setValue(dom, row.querySelector(".march-input"), "100");
    assert.equal(display.value, "（ペットなし）");
    setValue(dom, select, "1", "change");
    assert.equal(display.value, "87"); // 100 ÷ 1.15 = 86.95…
    setValue(dom, select, "8", "change");
    assert.equal(display.value, "77"); // 100 ÷ 1.30 = 76.92…
  });

  test("「全員同じ」をオンにすると共通の採用値へそろえ、行ごとの採用を変更できなくする（SIEGE-008）", t => {
    const dom = open(t);
    const boxes = () => $$(dom, ".use-pet-checkbox");
    setChecked(boxes()[2], false);
    assert.equal($(dom, "#petSameValueLabel").style.display, "none");
    setChecked($(dom, "#petSameAllCheckbox"), true);
    assert.notEqual($(dom, "#petSameValueLabel").style.display, "none");
    assert.ok(boxes().every(box => box.disabled && box.checked));
    setChecked($(dom, "#petSameValueCheckbox"), false);
    assert.ok(boxes().every(box => box.disabled && !box.checked));
    assert.ok(readJson(dom, "siegeCalcState").members.every(m => m.usePet === false));
    setChecked($(dom, "#petSameAllCheckbox"), false);
    assert.equal($(dom, "#petSameValueLabel").style.display, "none");
    assert.ok(boxes().every(box => !box.disabled));
  });

  test("「全員同じ」でペットなしにすると、速度ペットがあってもペットなしの行軍秒数で計算する（SIEGE-008、SIEGE-019）", t => {
    const dom = open(t);
    fillSiege(dom, { ...EXAMPLE1, petSame: false });
    const { output, reference } = calculate(dom);
    assert.match(output, /→ ①B（5分集結）※行軍100秒/);
    assert.deepEqual(checkProperties({ ...EXAMPLE1, petSame: false }, output, reference), []);
  });
});

test.describe("速度ペットのボーナス（SIEGE-009、SIEGE-046）", () => {
  const inputs = dom => $$(dom, "#petBonusEditor input[data-lv]");
  const badge = dom => $(dom, "#petBonusEditor .pb-changed").textContent;

  test("Lvごとのボーナスを編集して保存し、プルダウンと行軍秒数と計算結果へ反映する", t => {
    const dom = open(t);
    assert.match($(dom, "#petBonusEditor summary").textContent, /速度ペットのボーナス%を編集する（このブラウザだけ）/);
    assert.deepEqual(inputs(dom).map(input => [input.dataset.lv, input.value]),
      [1, 2, 3, 4, 5, 6, 7, 8].map(lv => [String(lv), String(DEFAULT_PET_BONUS[lv])]));
    assert.equal(badge(dom), "");

    fillSiege(dom, EXAMPLE1);
    calculate(dom);
    setValue(dom, inputs(dom)[7], "40", "change");
    assert.deepEqual(readJson(dom, "ksMarchPetBonus"), [0, 15, 17, 19, 21, 23, 25, 27, 40]);
    assert.equal(badge(dom), "※初期値から変更中");
    const row = rowOf(dom, "B");
    assert.equal(row.querySelector(".pet-select option[value='8']").textContent, "Lv8（+40%）");
    assert.equal(row.querySelector(".march-pet-output").value, "71"); // 100 ÷ 1.4 = 71.42…
    // 計算結果を表示しているため、計算し直す。①のTは max(330, 300+71, 239, 218) = 371。
    assert.match($(dom, "#output").textContent, /^①A\+B→メイン→増援\n0分00秒 → ①B（5分集結）※行軍71秒（6分11秒着、7分22秒帰還）\n/);

    // 0.1刻みの値も使う。
    setValue(dom, inputs(dom)[0], "12.5", "change");
    assert.deepEqual(readJson(dom, "ksMarchPetBonus"), [0, 12.5, 17, 19, 21, 23, 25, 27, 40]);
  });

  test("0以上の数でない入力は無視し、直前の値を保つ", t => {
    const dom = open(t);
    setValue(dom, inputs(dom)[7], "40", "change");
    for (const wrong of ["-5", "", "abc"]) {
      setValue(dom, inputs(dom)[7], wrong, "change");
      assert.deepEqual(readJson(dom, "ksMarchPetBonus"), [0, 15, 17, 19, 21, 23, 25, 27, 40], wrong);
      assert.equal(rowOf(dom, "A").querySelector(".pet-select option[value='8']").textContent, "Lv8（+40%）");
    }
  });

  test("計算結果を表示していなければ、編集しても結果カードを出さない", t => {
    const dom = open(t);
    setValue(dom, inputs(dom)[0], "20", "change");
    assert.equal($(dom, "#outputCard").style.display, "none");
  });

  test("「初期値に戻す」で既定値へ戻し、保存のキーを削除する", t => {
    const dom = open(t);
    fillSiege(dom, EXAMPLE1);
    setValue(dom, inputs(dom)[7], "40", "change");
    calculate(dom);
    $(dom, "#petBonusEditor .pb-reset").click();
    assert.equal(dom.window.localStorage.getItem("ksMarchPetBonus"), null);
    assert.equal(badge(dom), "");
    assert.deepEqual(inputs(dom).map(input => input.value), DEFAULT_PET_BONUS.slice(1).map(String));
    assert.equal(rowOf(dom, "B").querySelector(".march-pet-output").value, "77");
    assert.equal($(dom, "#output").textContent, EXAMPLE1_OUTPUT);
  });

  test("保存したボーナスを読み、9個の0以上の数でなければ既定値を使う", t => {
    const custom = [0, 10, 20, 30, 40, 50, 60, 70, 80.5];
    const valid = open(t, { storage: { ksMarchPetBonus: JSON.stringify(custom) } });
    assert.deepEqual(inputs(valid).map(input => Number(input.value)), custom.slice(1));
    assert.equal(badge(valid), "※初期値から変更中");
    assert.equal($(valid, ".pet-select option[value='8']").textContent, "Lv8（+80.5%）");

    for (const broken of [
      JSON.stringify(custom.slice(0, 8)),
      JSON.stringify([...custom, 90]),
      JSON.stringify([0, 10, 20, -30, 40, 50, 60, 70, 80]),
      JSON.stringify([0, 10, 20, "30", 40, 50, 60, 70, 80]),
      JSON.stringify({ 0: 0 }),
      "{壊れたJSON",
    ]) {
      const dom = open(t, { storage: { ksMarchPetBonus: broken } });
      assert.deepEqual(inputs(dom).map(input => Number(input.value)), DEFAULT_PET_BONUS.slice(1), broken);
      assert.equal(badge(dom), "", broken);
    }
  });
});

test.describe("保存と周期ウェーブタイマーへ渡す結果（SIEGE-031〜SIEGE-046）", () => {
  test("入力を変更のたびに保存し、次回表示で復元する。計算結果は保存せず、結果カードを出さない（SIEGE-040、SIEGE-041）", t => {
    const dom = open(t);
    fillSiege(dom, { ...EXAMPLE1, petSame: true });
    const { output } = calculate(dom);
    const state = readJson(dom, "siegeCalcState");
    assert.deepEqual(Object.keys(state).sort(),
      ["memberSeq", "members", "patternSeq", "patterns", "petSameForAll", "petSameValue", "settings"]);
    assert.deepEqual(Object.keys(state.members[0]).sort(), ["id", "label", "march", "petLevel", "role", "usePet"]);
    assert.deepEqual(Object.keys(state.patterns[0]).sort(), ["id", "kezuriIds", "name", "reinforceIds"]);
    assert.deepEqual(state.settings, { kezuriRallyMin: "5", mainRallyMin: "3", phaseGap: "1", buffer: "30" });
    assert.deepEqual([state.petSameForAll, state.petSameValue], [true, true]);
    assert.ok(!JSON.stringify(state).includes("周期"));

    const reopened = open(t, { storage: storageOf(dom) });
    assert.equal($(reopened, "#outputCard").style.display, "none");
    assert.deepEqual(memberRows(reopened), EXAMPLE1.members.map(m => [m.role, m.label]));
    assert.deepEqual(patternSelections(reopened), [["①", ["A", "B"], ["R"]], ["②", ["C"], []]]);
    assert.equal($(reopened, "#petSameAllCheckbox").checked, true);
    assert.equal(rowOf(reopened, "B").querySelector(".pet-select").value, "8");
    assert.equal(calculate(reopened).output, output);
  });

  test("パターン名と共通設定の変更も保存する（SIEGE-040）", t => {
    const dom = open(t);
    setValue(dom, $(dom, ".pattern-name-input"), "⑤");
    setValue(dom, $(dom, "#buffer"), "45");
    const state = readJson(dom, "siegeCalcState");
    assert.equal(state.patterns[0].name, "⑤");
    assert.equal(state.settings.buffer, "45");
  });

  test("reinforceIds、petLevel、usePetがない保存データは、増援を全員選び、速度ペットなし、採用オンとして読む（SIEGE-041）", t => {
    const state = {
      memberSeq: 4,
      patternSeq: 2,
      members: [
        { id: "m1", role: "メイン", label: "M", march: 10 },
        { id: "m2", role: "増援", label: "R1", march: 20 },
        { id: "m3", role: "増援", label: "R2", march: 30 },
        { id: "m4", role: "削り", label: "A", march: 40 },
      ],
      patterns: [{ id: "p1", name: "①", kezuriIds: ["m4"] }, { id: "p2", name: "②", kezuriIds: [], reinforceIds: ["m3"] }],
      settings: { kezuriRallyMin: "4", mainRallyMin: "2", phaseGap: "0", buffer: "5" },
    };
    const dom = open(t, { storage: { siegeCalcState: JSON.stringify(state) } });
    assert.deepEqual(patternSelections(dom), [["①", ["A"], ["R1", "R2"]], ["②", [], ["R2"]]]);
    assert.ok($$(dom, ".pet-select").every(select => select.value === "0"));
    assert.ok($$(dom, ".use-pet-checkbox").every(box => box.checked && !box.disabled));
    assert.equal($(dom, "#kezuriRallyMin").value, "4");
    const saved = readJson(dom, "siegeCalcState");
    assert.deepEqual(saved.patterns[0].reinforceIds, ["m2", "m3"]);
    assert.ok(saved.members.every(m => m.petLevel === 0 && m.usePet === true));
    // 追加したメンバーは保存した連番の続きのidを使う。
    $(dom, "#addMemberBtn").click();
    assert.equal(readJson(dom, "siegeCalcState").members.pop().id, "m5");
  });

  test("計算のたびに、周期、1周目の帰還の最大値、1周目の本文を保存時刻とともに渡す（SIEGE-035、SIEGE-045）", t => {
    const dom = open(t);
    fillSiege(dom, EXAMPLE1);
    const before = Date.now();
    calculate(dom);
    const after = Date.now();
    const saved = readJson(dom, "siegeTimelineForWaveTimer");
    assert.deepEqual(Object.keys(saved).sort(), ["maxSec", "periodSec", "rawText", "savedAt"]);
    assert.ok(saved.savedAt >= before && saved.savedAt <= after, String(saved.savedAt));
    // 1周目の帰還の最大値は②のMの12分48秒（768秒）。
    assert.deepEqual({ ...saved, savedAt: 0 }, { savedAt: 0, periodSec: 660, maxSec: 768, rawText: EXAMPLE1_OUTPUT });

    setValue(dom, $(dom, "#buffer"), "0");
    const { output } = calculate(dom);
    const next = readJson(dom, "siegeTimelineForWaveTimer");
    assert.ok(next.savedAt >= saved.savedAt);
    assert.equal(next.rawText, output);
    assert.notEqual(next.rawText, EXAMPLE1_OUTPUT);
  });

  test("計算するまでは、周期ウェーブタイマーへ渡す結果を保存しない（SIEGE-035）", t => {
    const dom = open(t);
    fillSiege(dom, EXAMPLE1);
    assert.equal(dom.window.localStorage.getItem("siegeTimelineForWaveTimer"), null);
  });

  for (const [name, failure] of Object.entries(STORAGE_FAILURES)) {
    test(`localStorageを使えなくても、入力、計算、ペットの編集ができる（COM-041、${name}）`, t => {
      const dom = open(t, { beforeParse: failure });
      // 故障を注入できたことを先に確かめ、検査が空回りしないようにする。
      if (name === "getterThrows") assert.throws(() => dom.window.localStorage);
      assert.equal($$(dom, "#memberBody tr").length, 8);
      fillSiege(dom, EXAMPLE1);
      assert.equal(calculate(dom).output, EXAMPLE1_OUTPUT);
      const lv8 = $(dom, '.pb-edit input[data-lv="8"]');
      setValue(dom, lv8, "40", "change");
      assert.ok($(dom, ".pet-select").innerHTML.includes("Lv8（+40%）"));
      if (name === "setItemThrows") assert.deepEqual(storageOf(dom), {});
    });
  }

  test("「Discord用にコピー」で1周目の出力をコピーし、1.5秒間「コピーしました」と表示する（SIEGE-031）", async t => {
    const clock = createClock();
    const copied = [];
    const dom = open(t, { clock, clipboard: { writeText: text => { copied.push(text); return Promise.resolve(); } } });
    fillSiege(dom, EXAMPLE1);
    calculate(dom);
    $(dom, "#copyBtn").click();
    await new Promise(resolve => setImmediate(resolve));
    assert.deepEqual(copied, [EXAMPLE1_OUTPUT]);
    assert.equal($(dom, "#copyBtn").textContent, "コピーしました");
    clock.advance(1499);
    assert.equal($(dom, "#copyBtn").textContent, "コピーしました");
    clock.advance(1);
    assert.equal($(dom, "#copyBtn").textContent, "Discord用にコピー");
  });
});
