"use strict";
// 集結タイムライン計算（web/攻城タイムライン計算.html）を実物のまま動かす検査。
// 要件IDはdocs/requirements/web-tools/siege-timeline.mdを参照する。

const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const assert = require("node:assert/strict");
const {
  openSiege, storageOf, setValue, $, $$, tabs, selectedTab, clickTab,
  fillSiege, calculate, createRandom, randomSiegeCase,
} = require("./helpers");
const { checkProperties, parseReference } = require("./siege-properties");
const { CASES, SHARDS, SEED, shardCases } = require("./siege-random");

const EXAMPLE_1 = {
  settings: { kz: 5, mr: 3, gap: 1, buf: 30 },
  members: [
    ["メイン", "M", 10], ["増援", "R", 10],
    ["削り", "A", 30], ["削り", "B", 20], ["削り", "C", 10],
    ["削り", "D", 5], ["削り", "E", 15], ["削り", "F", 25],
  ],
  patterns: [["A", "B", "C"], ["D"], ["E", "F"]],
};
const EXAMPLE_2 = {
  settings: { kz: 5, mr: 2, gap: 3, buf: 15 },
  members: [
    ["メイン", "M0", 0],
    ["削り", "K0", 9], ["削り", "K1", 11], ["削り", "K2", 126], ["削り", "K3", 75],
    ["削り", "K4", 37], ["削り", "K5", 126], ["削り", "K6", 140], ["削り", "K7", 44],
  ],
  patterns: [["K0", "K3"], ["K4"], ["K2", "K4", "K5", "K6"]],
};
const EXAMPLE_3 = {
  settings: { kz: 5, mr: 2, gap: 2, buf: 40 },
  members: [
    ["メイン", "M0", 48], ["メイン", "M1", 44],
    ["削り", "K0", 145], ["削り", "K1", 18], ["削り", "K2", 4], ["削り", "K3", 110],
  ],
  patterns: [["K3"], ["K0", "K2"]],
};

function run(testCase, dom = openSiege()) {
  fillSiege(dom, testCase);
  return calculate(dom);
}

function savedTabs(dom) {
  return JSON.parse(dom.window.localStorage.getItem("siegeCalcTabs"));
}

test.describe("計算規則（SIEGE-011〜SIEGE-021）", () => {
  test("例1: 定義順に確定し、周期は全員の待ち時間を守る最小値になる", t => {
    const dom = openSiege();
    t.after(() => dom.window.close());
    const { output, reference } = run(EXAMPLE_1, dom);

    assert.deepEqual(checkProperties(EXAMPLE_1, output, reference), []);
    // 出力の書式（SIEGE-020、SIEGE-024）は周期ウェーブタイマーが読むため変えない。
    assert.equal(output, [
      "①A+B+C→メイン→増援",
      "0分00秒 → A（5分集結）※行軍30秒（5分30秒着、6分00秒帰還）",
      "0分10秒 → B（5分集結）※行軍20秒（5分30秒着、5分50秒帰還）",
      "0分20秒 → C（5分集結）※行軍10秒（5分30秒着、5分40秒帰還）",
      "2分21秒 → M（3分集結）※行軍10秒（5分31秒着、5分41秒帰還）",
      "2分22秒 → R（3分集結）※行軍10秒（5分32秒着、5分42秒帰還）",
      "",
      "②D→メイン→増援",
      "4分15秒 → D（5分集結）※行軍5秒（9分20秒着、9分25秒帰還）",
      "6分11秒 → M（3分集結）※行軍10秒（9分21秒着、9分31秒帰還）",
      "6分12秒 → R（3分集結）※行軍10秒（9分22秒着、9分32秒帰還）",
      "",
      "③E+F→メイン→増援",
      "7分55秒 → E（5分集結）※行軍15秒（13分10秒着、13分25秒帰還）",
      "7分45秒 → F（5分集結）※行軍25秒（13分10秒着、13分35秒帰還）",
      "10分01秒 → M（3分集結）※行軍10秒（13分11秒着、13分21秒帰還）",
      "10分02秒 → R（3分集結）※行軍10秒（13分12秒着、13分22秒帰還）",
      "",
      "周期：11分30秒",
    ].join("\n"));
    // 2周目は1周目の全時刻へ周期を足したもの（SIEGE-021）。
    const { rounds } = parseReference(reference);
    assert.equal(rounds[1][0].lines[0].launch, 0 + 690);
    assert.equal(rounds[1][2].lines[3].ret, 802 + 690);
  });

  test("性質の検査は、周期が短すぎる出力と2周目の時刻のずれを違反として検出する", t => {
    const dom = openSiege();
    t.after(() => dom.window.close());
    const { output, reference } = run(EXAMPLE_1, dom);
    // 以前の実装は例1で周期を7分40秒と出していた。
    const shortCycle = text => text.replace("周期：11分30秒", "周期：7分40秒");
    const violations = checkProperties(EXAMPLE_1, shortCycle(output), shortCycle(reference));
    assert.ok(violations.some(v => v.startsWith("C5:")), violations.join("\n"));
    assert.ok(violations.some(v => v.startsWith("C6:")), violations.join("\n"));
    const shifted = reference.replace(/【2周目】\n①A\+B\+C→メイン→増援\n11分30秒/, "【2周目】\n①A+B+C→メイン→増援\n11分00秒");
    assert.notEqual(shifted, reference);
    assert.ok(checkProperties(EXAMPLE_1, output, shifted).some(v => v.startsWith("C3:")));
  });

  test("性質の検査は、負の時刻、待ち時間の違反、出力の不一致、構成の違いを検出する", t => {
    const dom = openSiege();
    t.after(() => dom.window.close());
    const { output, reference } = run(EXAMPLE_1, dom);
    const has = (violations, name) => violations.some(v => v.startsWith(name + ":"));

    // C1: 負の時刻
    const negative = reference.replace("\n0分00秒 → A", "\n-1分00秒 → A");
    assert.notEqual(negative, reference);
    assert.ok(has(checkProperties(EXAMPLE_1, output, negative), "C1"));
    // C2: 同じ出力でもバッファが長ければ、次の発起が帰還+バッファより早い
    const longBuffer = { ...EXAMPLE_1, settings: { ...EXAMPLE_1.settings, buf: 600 } };
    assert.ok(has(checkProperties(longBuffer, output, reference), "C2"));
    // C8: 1周目の出力が参考の1周目と食い違う
    const edited = output.replace("0分10秒 → B", "0分11秒 → B");
    assert.notEqual(edited, output);
    assert.ok(has(checkProperties(EXAMPLE_1, edited, reference), "C8"));
    // C9: 入力と違うパターン数、削りの欠落、増援の欠落
    assert.ok(has(checkProperties({ ...EXAMPLE_1, patterns: [["A", "B", "C"], ["D"]] }, output, reference), "C9"));
    assert.ok(has(checkProperties({ ...EXAMPLE_1, patterns: [["A", "B", "C", "F"], ["D"], ["E", "F"]] }, output, reference), "C9"));
    const withoutReinforcement = reference.replace(/\n2分22秒 → R（[^\n]+/, "");
    assert.notEqual(withoutReinforcement, reference);
    assert.ok(has(checkProperties(EXAMPLE_1, output, withoutReinforcement), "C9"));
  });

  test("性質の検査は、必要以上に遅い着弾（C10）を検出する", t => {
    const dom = openSiege();
    t.after(() => dom.window.close());
    const { output, reference } = run(EXAMPLE_2, dom);
    const shiftTimes = (text, seconds) => text.replace(/(\d+)分(\d{2})秒/g, (_, m, s) => {
      const total = Number(m) * 60 + Number(s) + seconds;
      return `${Math.floor(total / 60)}分${String(total % 60).padStart(2, "0")}秒`;
    });
    // 1周目の③だけを全員1秒遅らせる。参考と出力の両方で同じに変えるため、C8は成り立つ。
    const start = reference.indexOf("\n③");
    const end = reference.indexOf("\n【2周目】");
    const late = reference.slice(0, start) + shiftTimes(reference.slice(start, end), 1) + reference.slice(end);
    const lateOutput = `${late.split("\n【2周目】\n")[0].replace(/^【1周目】\n/, "")}\n${output.split("\n").pop()}`;
    const violations = checkProperties(EXAMPLE_2, lateOutput, late);
    assert.ok(violations.some(v => v.startsWith("C10:")), violations.join("\n"));
    assert.ok(!violations.some(v => v.startsWith("C8:")), violations.join("\n"));

    // 2周とも全時刻を1秒遅らせると、周期と時刻の差は変わらずC1〜C9は成り立ち、C10だけが違反になる。
    const cycleLine = output.split("\n").pop();
    const allLate = shiftTimes(reference.replace(/\n周期：.+$/, ""), 1) + "\n" + cycleLine;
    const allLateOutput = shiftTimes(output.replace(/\n周期：.+$/, ""), 1) + "\n" + cycleLine;
    const onlyC10 = checkProperties(EXAMPLE_2, allLateOutput, allLate);
    assert.ok(onlyC10.length > 0);
    assert.deepEqual([...new Set(onlyC10.map(v => v.split(":")[0]))], ["C10"], onlyC10.join("\n"));
  });

  test("性質の検査は、必要以上に長い周期（C7）と2周目の順番の入れ替わり（C4）を検出する", t => {
    const dom = openSiege();
    t.after(() => dom.window.close());
    const { output, reference } = run(EXAMPLE_1, dom);
    const has = (violations, name) => violations.some(v => v.startsWith(name + ":"));
    const shiftTimes = (text, seconds) => text.replace(/(\d+)分(\d{2})秒/g, (_, m, s) => {
      const total = Number(m) * 60 + Number(s) + seconds;
      return `${Math.floor(total / 60)}分${String(total % 60).padStart(2, "0")}秒`;
    });
    const [firstRound, secondRound] = reference.split("【2周目】");

    // 周期と2周目の全時刻を60秒遅らせても、C1〜C6とC8は成り立ち、C7だけが違反になる。
    const longCycle = text => text.replace("周期：11分30秒", "周期：12分30秒");
    const late = `${firstRound}【2周目】${shiftTimes(secondRound.replace(/\n周期：.+$/, ""), 60)}\n周期：12分30秒`;
    assert.deepEqual(checkProperties(EXAMPLE_1, longCycle(output), late).map(v => v.split(":")[0]), ["C7"]);

    // 2周目の①だけを大きく遅らせると、2周目の順番が1周目と変わる。
    const [beforeSecond, afterFirstPattern] = secondRound.split("\n②");
    const reordered = `${firstRound}【2周目】${shiftTimes(beforeSecond, 3000)}\n②${afterFirstPattern}`;
    assert.ok(has(checkProperties(EXAMPLE_1, output, reordered), "C4"));
  });

  test("削りを選んでいないパターンを途中に含んでも、メインと増援で着弾を決める（SIEGE-012、SIEGE-024）", t => {
    const dom = openSiege();
    t.after(() => dom.window.close());
    const testCase = {
      settings: { kz: 5, mr: 3, gap: 1, buf: 30 },
      members: [["メイン", "M", 10], ["増援", "R", 10], ["削り", "A", 30], ["削り", "B", 20]],
      patterns: [["A"], [], ["B"]],
    };
    const { output, reference } = run(testCase, dom);
    assert.deepEqual(checkProperties(testCase, output, reference), []);
    assert.equal(output, [
      "①A→メイン→増援",
      "0分00秒 → A（5分集結）※行軍30秒（5分30秒着、6分00秒帰還）",
      "2分21秒 → M（3分集結）※行軍10秒（5分31秒着、5分41秒帰還）",
      "2分22秒 → R（3分集結）※行軍10秒（5分32秒着、5分42秒帰還）",
      "",
      "②→メイン→増援",
      "6分11秒 → M（3分集結）※行軍10秒（9分21秒着、9分31秒帰還）",
      "6分12秒 → R（3分集結）※行軍10秒（9分22秒着、9分32秒帰還）",
      "",
      "③B→メイン→増援",
      "7分50秒 → B（5分集結）※行軍20秒（13分10秒着、13分30秒帰還）",
      "10分01秒 → M（3分集結）※行軍10秒（13分11秒着、13分21秒帰還）",
      "10分02秒 → R（3分集結）※行軍10秒（13分12秒着、13分22秒帰還）",
      "",
      "周期：11分30秒",
    ].join("\n"));
  });

  test("削りを選んでいないパターンを含む決定的な乱数の入力100件でも、性質C1〜C10に違反しない", t => {
    // 既存の1000件（siege-random.js）の入力を変えないよう、別のSeedで空のパターンを許して作る。
    const rnd = createRandom(2468);
    const dom = openSiege();
    t.after(() => dom.window.close());
    const failures = [];
    let empty = 0;
    let emptyFirst = 0;
    let allEmpty = 0;
    for (let i = 0; i < 100; i++) {
      const testCase = randomSiegeCase(rnd, { allowEmptyPattern: true });
      empty += testCase.patterns.filter(p => p.length === 0).length;
      if (testCase.patterns[0].length === 0) emptyFirst++;
      if (testCase.patterns.every(p => p.length === 0)) allEmpty++;
      const { output, reference } = run(testCase, dom);
      const violations = checkProperties(testCase, output, reference);
      if (violations.length) failures.push({ index: i, testCase, violations });
    }
    assert.ok(empty > 0, "空のパターンが1件もない");
    assert.ok(emptyFirst > 0, "先頭が空の入力が1件もない");
    assert.ok(allEmpty > 0, "すべて空の入力が1件もない");
    assert.deepEqual(failures.slice(0, 3), [], `違反した入力は${failures.length}件`);
  });

  test("例2: 同じ削りが複数のパターンに入っても性質を満たす", t => {
    const dom = openSiege();
    t.after(() => dom.window.close());
    const { output, reference } = run(EXAMPLE_2, dom);
    assert.deepEqual(checkProperties(EXAMPLE_2, output, reference), []);
  });

  test("例3: パターンごとに戻りの間隔が違っても周期は630秒になる", t => {
    const dom = openSiege();
    t.after(() => dom.window.close());
    const { output, reference } = run(EXAMPLE_3, dom);
    assert.deepEqual(checkProperties(EXAMPLE_3, output, reference), []);
    assert.match(output, /\n周期：10分30秒$/);
  });

  test("決定的な乱数の入力は1000件以上を、分けたファイルで漏れなく検査する", () => {
    // 検査の本体はsiege-random-{番号}.test.jsにある。
    assert.ok(CASES >= 1000);
    const indexes = [];
    for (let shard = 1; shard <= SHARDS; shard++) {
      const file = path.join(__dirname, `siege-random-${shard}.test.js`);
      assert.ok(fs.existsSync(file), `shard ${shard}`);
      // 複写の誤りで同じ組を2回検査し、別の組を検査しない事態を防ぐ。
      assert.match(fs.readFileSync(file, "utf8"), new RegExp(`\\.runShard\\(${shard}\\);`));
      indexes.push(...shardCases(shard).map(c => c.index));
    }
    assert.deepEqual(indexes.sort((a, b) => a - b), Array.from({ length: CASES }, (_, i) => i));
    const shardFiles = fs.readdirSync(__dirname).filter(name => /^siege-random-\d+\.test\.js$/.test(name));
    assert.equal(shardFiles.length, SHARDS);
  });

  test("乱数の入力はメイン1〜2人、増援0〜2人、削り1〜8人、パターン1〜5件の範囲にある", () => {
    const rnd = createRandom(SEED);
    const seen = { reinforcements: new Set(), patterns: new Set() };
    for (let i = 0; i < CASES; i++) {
      const { members, patterns } = randomSiegeCase(rnd);
      const count = role => members.filter(m => m[0] === role).length;
      assert.ok(count("メイン") >= 1 && count("メイン") <= 2);
      assert.ok(count("削り") >= 1 && count("削り") <= 8);
      seen.reinforcements.add(count("増援"));
      seen.patterns.add(patterns.length);
    }
    // 増援なしの編成（D8）と複数パターンを含むことを確かめる。
    assert.deepEqual([...seen.reinforcements].sort(), [0, 1, 2]);
    assert.deepEqual([...seen.patterns].sort(), [1, 2, 3, 4, 5]);
  });

  test("増援が0人でも計算する（SIEGE-018）", t => {
    const dom = openSiege();
    t.after(() => dom.window.close());
    const { output, reference } = run(EXAMPLE_3, dom);
    assert.doesNotMatch(output, /メインの?メンバーがいません/);
    assert.deepEqual(checkProperties(EXAMPLE_3, output, reference), []);
  });

  test("メインが0人の場合は計算せずに知らせ、前回の参考結果は残す（SIEGE-033、SIEGE-034）", t => {
    const dom = openSiege();
    t.after(() => dom.window.close());
    const previous = run(EXAMPLE_1, dom);
    const noMain = {
      settings: EXAMPLE_1.settings,
      members: EXAMPLE_1.members.filter(m => m[0] !== "メイン"),
      patterns: EXAMPLE_1.patterns,
    };
    const { output, reference } = run(noMain, dom);
    assert.equal(output, "メイン役割のメンバーがいません");
    // 利用者の決定（2026-10-25）: 前回の参考結果は表示したまま保存する。
    assert.equal(reference, previous.reference);
    assert.equal($(dom, "#refOutputCard").style.display, "block");
    const saved = savedTabs(dom).tabs[0].result;
    assert.equal(saved.ok, false);
    assert.equal(saved.output, "メイン役割のメンバーがいません");
    assert.equal(saved.reference, previous.reference);
  });

  test("パターンが0件の場合は計算せずに知らせ、前回の参考結果は残す（SIEGE-032、SIEGE-034）", t => {
    const dom = openSiege();
    t.after(() => dom.window.close());
    const previous = run(EXAMPLE_1, dom);
    const { output, reference } = run({ ...EXAMPLE_1, patterns: [] }, dom);
    assert.equal(output, "パターンが設定されていません。");
    assert.equal(reference, previous.reference);
    assert.equal($(dom, "#refOutputCard").style.display, "block");
    const saved = savedTabs(dom).tabs[0].result;
    assert.equal(saved.ok, false);
    assert.equal(saved.reference, previous.reference);
  });
});

test.describe("タブ（SIEGE-050〜SIEGE-054）", () => {
  test("初回はサンプルの入ったタブ「計算1」を1つ表示する（SIEGE-006、SIEGE-042）", t => {
    const dom = openSiege();
    t.after(() => dom.window.close());
    assert.deepEqual(tabs(dom).map(tab => tab.textContent), ["計算1"]);
    assert.equal(selectedTab(dom).textContent, "計算1");
    assert.equal($$(dom, "#memberBody tr").length, 8);
    assert.equal($$(dom, ".pattern-block").length, 3);
    assert.equal($(dom, "#deleteTabBtn").disabled, true);
    assert.equal($(dom, "#outputCard").style.display, "none");
  });

  test("追加したタブは入力も計算結果も独立している", t => {
    const dom = openSiege();
    t.after(() => dom.window.close());
    fillSiege(dom, EXAMPLE_1);
    const first = calculate(dom).output;

    $(dom, "#addTabBtn").click();
    assert.deepEqual(tabs(dom).map(tab => tab.textContent), ["計算1", "計算2"]);
    assert.equal(selectedTab(dom).textContent, "計算2");
    // 新しいタブは表示中のタブの入力を複製して始め、計算結果は写さない（SIEGE-051）。
    assert.deepEqual($$(dom, ".label-input").map(input => input.value), EXAMPLE_1.members.map(m => m[1]));
    assert.deepEqual($$(dom, ".march-input").map(input => input.value), EXAMPLE_1.members.map(m => String(m[2])));
    assert.deepEqual(
      $$(dom, ".pattern-block").map(block => Array.from(block.querySelectorAll("input:checked")).map(box => box.parentElement.textContent.trim())),
      EXAMPLE_1.patterns);
    assert.equal($(dom, "#kezuriRallyMin").value, "5");
    assert.equal($(dom, "#buffer").value, "30");
    assert.equal($(dom, "#outputCard").style.display, "none");
    assert.equal(calculate(dom).output, first);

    fillSiege(dom, EXAMPLE_3);
    const second = calculate(dom).output;
    assert.notEqual(second, first);

    clickTab(dom, 0);
    assert.equal($(dom, "#output").textContent, first);
    assert.equal($(dom, "#mainRallyMin").value, "3");
    // 複製先の編集（パターンの削除と選択の変更）は、複製元へ及ばない。
    assert.equal($$(dom, ".pattern-block").length, 3);
    assert.equal(calculate(dom).output, first);
    assert.deepEqual($$(dom, ".label-input").map(input => input.value), EXAMPLE_1.members.map(m => m[1]));

    clickTab(dom, 1);
    assert.equal($(dom, "#output").textContent, second);
    assert.equal($(dom, "#mainRallyMin").value, "2");
  });

  test("名前を変更でき、空にすると既定の名前を表示する", t => {
    const dom = openSiege();
    t.after(() => dom.window.close());
    $(dom, "#addTabBtn").click();
    setValue(dom, $(dom, "#tabNameInput"), "本隊");
    assert.deepEqual(tabs(dom).map(tab => tab.textContent), ["計算1", "本隊"]);
    setValue(dom, $(dom, "#tabNameInput"), "");
    assert.deepEqual(tabs(dom).map(tab => tab.textContent), ["計算1", "計算2"]);
    clickTab(dom, 0);
    assert.equal($(dom, "#tabNameInput").value, "計算1");
  });

  test("削除は確認を取り、取り消せば何も変えない。番号は再利用しない", t => {
    let answer = false;
    const asked = [];
    const dom = openSiege({ confirm: message => { asked.push(message); return answer; } });
    t.after(() => dom.window.close());
    $(dom, "#addTabBtn").click();
    $(dom, "#addTabBtn").click();
    clickTab(dom, 1);

    $(dom, "#deleteTabBtn").click();
    assert.equal(asked.length, 1);
    assert.match(asked[0], /計算2/);
    assert.equal(tabs(dom).length, 3);

    answer = true;
    $(dom, "#deleteTabBtn").click();
    assert.deepEqual(tabs(dom).map(tab => tab.textContent), ["計算1", "計算3"]);
    // 右隣のタブを表示する。
    assert.equal(selectedTab(dom).textContent, "計算3");
    $(dom, "#deleteTabBtn").click();
    assert.equal(selectedTab(dom).textContent, "計算1");
    assert.equal($(dom, "#deleteTabBtn").disabled, true);

    $(dom, "#addTabBtn").click();
    assert.deepEqual(tabs(dom).map(tab => tab.textContent), ["計算1", "計算4"]);
  });

  test("矢印キー、Home、Endでタブを切り替え、Focusを移す", t => {
    const dom = openSiege();
    t.after(() => dom.window.close());
    $(dom, "#addTabBtn").click();
    $(dom, "#addTabBtn").click();
    clickTab(dom, 0);
    const press = key => dom.window.document.activeElement.dispatchEvent(
      new dom.window.KeyboardEvent("keydown", { key, bubbles: true }));

    tabs(dom)[0].focus();
    press("ArrowRight");
    assert.equal(selectedTab(dom).textContent, "計算2");
    assert.equal(dom.window.document.activeElement, selectedTab(dom));
    press("End");
    assert.equal(selectedTab(dom).textContent, "計算3");
    press("ArrowRight");
    assert.equal(selectedTab(dom).textContent, "計算1");
    press("ArrowLeft");
    assert.equal(selectedTab(dom).textContent, "計算3");
    press("Home");
    assert.equal(selectedTab(dom).textContent, "計算1");
    // 選ばれていないタブはTabキーの移動先にしない。
    assert.deepEqual(tabs(dom).map(tab => tab.tabIndex), [0, -1, -1]);
  });
});

test.describe("保存（SIEGE-040〜SIEGE-044）", () => {
  // 別のブラウザのタブで保存されたときと同じ通知を送る。
  function receiveOwnUpdate(target, source) {
    const value = source.window.localStorage.getItem("siegeCalcTabs");
    target.window.localStorage.setItem("siegeCalcTabs", value);
    target.window.dispatchEvent(new target.window.StorageEvent("storage", { key: "siegeCalcTabs", newValue: value }));
  }

  test("別のブラウザのタブで保存されたら読み直し、そのタブで作ったタブを上書きで消さない（SIEGE-044）", t => {
    const a = openSiege();
    t.after(() => a.window.close());
    const b = openSiege({ storage: storageOf(a) });
    t.after(() => b.window.close());

    // Aでタブを加えて計算する。Bは通知を受けて読み直す。
    $(a, "#addTabBtn").click();
    fillSiege(a, EXAMPLE_3);
    const added = calculate(a).output;
    receiveOwnUpdate(b, a);
    assert.deepEqual(tabs(b).map(tab => tab.textContent), ["計算1", "計算2"]);
    // Bは表示中のタブ（計算1）を表示し続ける。
    assert.equal(selectedTab(b).textContent, "計算1");

    // Bで入力を変えても、Aで加えたタブと計算結果は残る。
    setValue(b, $(b, "#buffer"), "45");
    const saved = savedTabs(b);
    assert.deepEqual(saved.tabs.map(x => x.name), ["計算1", "計算2"]);
    assert.equal(saved.tabs[1].result.output, added);
    assert.equal(saved.tabs[0].settings.buffer, "45");
  });

  test("別のブラウザのタブで表示中のタブが削除されたら、保存データの最後に表示していたタブを表示する（SIEGE-044）", t => {
    const a = openSiege();
    t.after(() => a.window.close());
    $(a, "#addTabBtn").click();
    $(a, "#addTabBtn").click();
    clickTab(a, 1);
    const b = openSiege({ storage: storageOf(a) });
    t.after(() => b.window.close());
    assert.equal(selectedTab(b).textContent, "計算2");
    // Aで計算2を削除すると、Aは右隣の計算3を表示して保存する。Bは先頭ではなく計算3を表示する。
    $(a, "#deleteTabBtn").click();
    receiveOwnUpdate(b, a);
    assert.deepEqual(tabs(b).map(tab => tab.textContent), ["計算1", "計算3"]);
    assert.equal(selectedTab(b).textContent, "計算3");
  });

  test("別のブラウザのタブで表示中のタブが変わったら、その内容へ置き換える（SIEGE-044）", t => {
    const a = openSiege();
    t.after(() => a.window.close());
    const b = openSiege({ storage: storageOf(a) });
    t.after(() => b.window.close());
    setValue(a, $(a, "#buffer"), "50");
    receiveOwnUpdate(b, a);
    assert.equal($(b, "#buffer").value, "50");
    setValue(b, $(b, "#phaseGap"), "2");
    const saved = savedTabs(b).tabs[0].settings;
    assert.deepEqual([saved.buffer, saved.phaseGap], ["50", "2"]);
  });

  test("読めない保存データの通知は無視する（SIEGE-044）", t => {
    const a = openSiege();
    t.after(() => a.window.close());
    $(a, "#addTabBtn").click();
    for (const broken of [null, "{壊れたJSON", '{"version":1,"tabs":[]}']) {
      if (broken === null) a.window.localStorage.removeItem("siegeCalcTabs");
      else a.window.localStorage.setItem("siegeCalcTabs", broken);
      a.window.dispatchEvent(new a.window.StorageEvent("storage", { key: "siegeCalcTabs", newValue: broken }));
      assert.deepEqual(tabs(a).map(tab => tab.textContent), ["計算1", "計算2"], String(broken));
      assert.equal(selectedTab(a).textContent, "計算2", String(broken));
    }
  });

  test("戻る操作でページが復元されたら、離れていた間の保存を読み直す（SIEGE-044）", t => {
    const a = openSiege();
    t.after(() => a.window.close());
    const b = openSiege({ storage: storageOf(a) });
    t.after(() => b.window.close());
    $(a, "#addTabBtn").click();
    // 通知を受けないまま、保存データだけが変わった状態で復元される。
    b.window.localStorage.setItem("siegeCalcTabs", a.window.localStorage.getItem("siegeCalcTabs"));
    const shown = new b.window.Event("pageshow");
    Object.defineProperty(shown, "persisted", { value: true });
    b.window.dispatchEvent(shown);
    assert.deepEqual(tabs(b).map(tab => tab.textContent), ["計算1", "計算2"]);
  });

  test("読み直しでは保存し直さず、通知が往復しない（SIEGE-044）", t => {
    const a = openSiege();
    t.after(() => a.window.close());
    const b = openSiege({ storage: storageOf(a) });
    t.after(() => b.window.close());
    $(a, "#addTabBtn").click();
    let writes = 0;
    const original = b.window.Storage.prototype.setItem;
    b.window.Storage.prototype.setItem = function (...args) { writes += 1; return original.apply(this, args); };
    const value = a.window.localStorage.getItem("siegeCalcTabs");
    original.call(b.window.localStorage, "siegeCalcTabs", value);
    b.window.dispatchEvent(new b.window.StorageEvent("storage", { key: "siegeCalcTabs", newValue: value }));
    assert.equal(writes, 0);
    assert.equal(b.window.localStorage.getItem("siegeCalcTabs"), value);
  });

  test("すべてのタブ、最後に表示したタブ、計算結果を保存して復元する", t => {
    const dom = openSiege();
    t.after(() => dom.window.close());
    fillSiege(dom, EXAMPLE_1);
    const first = calculate(dom);
    $(dom, "#addTabBtn").click();
    fillSiege(dom, EXAMPLE_3);
    setValue(dom, $(dom, "#tabNameInput"), "別動隊");
    clickTab(dom, 0);
    calculate(dom);

    const saved = savedTabs(dom);
    assert.equal(saved.version, 1);
    assert.equal(saved.tabs.length, 2);
    assert.equal(saved.activeTabId, saved.tabs[0].id);
    assert.equal(saved.tabs[0].result.revision, 2);
    assert.equal(saved.tabs[0].result.ok, true);
    assert.equal(saved.tabs[0].result.output, first.output);
    assert.equal(saved.tabs[0].result.reference, first.reference);
    assert.equal(saved.tabs[1].result, null);

    const reopened = openSiege({ storage: storageOf(dom) });
    t.after(() => reopened.window.close());
    assert.deepEqual(tabs(reopened).map(tab => tab.textContent), ["計算1", "別動隊"]);
    // タブのidは作るたびに変わる値のため、開き直しても保存したidを保つ（SIEGE-041）。
    assert.deepEqual(savedTabs(reopened).tabs.map(x => x.id), saved.tabs.map(x => x.id));
    saved.tabs.forEach(x => assert.match(x.id, /^t\d+-[0-9a-z]+$/));
    assert.notEqual(saved.tabs[0].id, saved.tabs[1].id);
    assert.equal(selectedTab(reopened).textContent, "計算1");
    assert.equal($(reopened, "#outputCard").style.display, "block");
    assert.equal($(reopened, "#output").textContent, first.output);
    assert.equal($(reopened, "#refOutput").textContent, first.reference);
    clickTab(reopened, 1);
    assert.deepEqual($$(reopened, ".label-input").map(input => input.value), EXAMPLE_3.members.map(m => m[1]));
    assert.equal($(reopened, "#buffer").value, "40");
    assert.equal($(reopened, "#outputCard").style.display, "none");
  });

  test("メンバーを0人にしたタブも、そのまま復元する", t => {
    const dom = openSiege();
    t.after(() => dom.window.close());
    let button;
    while ((button = $(dom, ".del-member-btn"))) button.click();
    const reopened = openSiege({ storage: storageOf(dom) });
    t.after(() => reopened.window.close());
    assert.equal($$(reopened, "#memberBody tr").length, 0);
  });

  test("旧キーsiegeCalcStateの入力を最初のタブへ移し、旧キーは変えない", t => {
    const legacy = JSON.stringify({
      memberSeq: 3,
      patternSeq: 1,
      members: [
        { id: "m1", role: "メイン", label: "主", march: 12 },
        { id: "m2", role: "削り", label: "甲", march: 40 },
        { id: "m3", role: "削り", label: "乙", march: 25 },
      ],
      patterns: [{ id: "p1", name: "①", kezuriIds: ["m2", "m3"] }],
      settings: { kezuriRallyMin: "4", mainRallyMin: "2", phaseGap: "2", buffer: "20" },
    });
    const dom = openSiege({ storage: { siegeCalcState: legacy } });
    t.after(() => dom.window.close());

    assert.deepEqual(tabs(dom).map(tab => tab.textContent), ["計算1"]);
    assert.deepEqual($$(dom, ".label-input").map(input => input.value), ["主", "甲", "乙"]);
    assert.deepEqual($$(dom, ".march-input").map(input => input.value), ["12", "40", "25"]);
    assert.deepEqual($$(dom, ".role-select").map(select => select.value), ["メイン", "削り", "削り"]);
    assert.deepEqual($$(dom, ".pattern-block input[type=checkbox]").map(box => box.checked), [true, true]);
    assert.equal($(dom, "#kezuriRallyMin").value, "4");
    assert.equal($(dom, "#mainRallyMin").value, "2");
    assert.equal($(dom, "#phaseGap").value, "2");
    assert.equal($(dom, "#buffer").value, "20");
    assert.equal(dom.window.localStorage.getItem("siegeCalcState"), legacy);

    // 移した後の追加でidが重ならない。
    $(dom, "#addMemberBtn").click();
    const ids = $$(dom, ".label-input").map(input => input.dataset.id);
    assert.equal(new Set(ids).size, ids.length);
    assert.equal(savedTabs(dom).tabs[0].members.length, 4);

    // 移した後に開き直しても、新しいキーを使い、移した後の編集を旧キーで上書きしない。
    const reopened = openSiege({ storage: storageOf(dom) });
    t.after(() => reopened.window.close());
    assert.equal(reopened.window.localStorage.getItem("siegeCalcState"), legacy);
    assert.equal($$(reopened, "#memberBody tr").length, 4);
    assert.equal($(reopened, "#kezuriRallyMin").value, "4");
  });

  test("旧キーにメンバーがいなくても、共通設定とパターンをそのまま移す", t => {
    const legacy = JSON.stringify({
      memberSeq: 2, patternSeq: 1, members: [],
      patterns: [{ id: "p1", name: "①", kezuriIds: [] }],
      settings: { kezuriRallyMin: "4", mainRallyMin: "2", phaseGap: "2", buffer: "20" },
    });
    const dom = openSiege({ storage: { siegeCalcState: legacy } });
    t.after(() => dom.window.close());
    assert.equal($$(dom, "#memberBody tr").length, 0);
    assert.equal($$(dom, ".pattern-block").length, 1);
    assert.equal($(dom, "#kezuriRallyMin").value, "4");
    assert.equal($(dom, "#buffer").value, "20");
    assert.equal(dom.window.localStorage.getItem("siegeCalcState"), legacy);
  });

  test("新しいキーが空か壊れていれば、旧キーから移し直す（SIEGE-042）", t => {
    const legacy = JSON.stringify({
      memberSeq: 1, patternSeq: 0,
      members: [{ id: "m1", role: "メイン", label: "主", march: 12 }],
      patterns: [], settings: { kezuriRallyMin: "4", mainRallyMin: "2", phaseGap: "2", buffer: "20" },
    });
    for (const broken of ["{壊れたJSON", '{"version":1,"tabs":[]}', ""]) {
      const dom = openSiege({ storage: { siegeCalcState: legacy, siegeCalcTabs: broken } });
      t.after(() => dom.window.close());
      assert.deepEqual($$(dom, ".label-input").map(input => input.value), ["主"], broken);
      assert.equal($(dom, "#kezuriRallyMin").value, "4", broken);
      assert.equal(dom.window.localStorage.getItem("siegeCalcState"), legacy, broken);
      assert.equal(savedTabs(dom).tabs[0].members.length, 1, broken);
    }
  });

  test("新しいキーが空か壊れていて旧キーもなければ、サンプルのタブを作る（SIEGE-006、SIEGE-042）", t => {
    for (const broken of ["{壊れたJSON", '{"version":1,"tabs":[]}', ""]) {
      const dom = openSiege({ storage: { siegeCalcTabs: broken } });
      t.after(() => dom.window.close());
      assert.equal($$(dom, "#memberBody tr").length, 8, broken);
      assert.equal($$(dom, ".pattern-block").length, 3, broken);
    }
  });

  test("旧キーも新しいキーもなければサンプルのタブを作る", t => {
    const dom = openSiege();
    t.after(() => dom.window.close());
    assert.equal($$(dom, "#memberBody tr").length, 8);
    assert.equal(dom.window.localStorage.getItem("siegeCalcState"), null);
  });

  test("計算した後に入力を変えると、計算し直すまで注意を表示する（SIEGE-043）", t => {
    const dom = openSiege();
    t.after(() => dom.window.close());
    const notice = () => $(dom, "#resultNotice").textContent;
    fillSiege(dom, EXAMPLE_1);
    const first = calculate(dom);
    assert.equal(notice(), "");

    setValue(dom, $(dom, ".march-input"), "11");
    assert.equal(notice(), "⚠ 入力が変更されています。計算し直してください");
    // 結果は消さない。
    assert.equal($(dom, "#output").textContent, first.output);
    // 再表示でも注意を出す。
    const reopened = openSiege({ storage: storageOf(dom) });
    t.after(() => reopened.window.close());
    assert.equal($(reopened, "#resultNotice").textContent, "⚠ 入力が変更されています。計算し直してください");

    // 元の値へ戻すか、計算し直すと注意を消す。
    setValue(dom, $(dom, ".march-input"), "10");
    assert.equal(notice(), "");
    setValue(dom, $(dom, "#buffer"), "45");
    assert.notEqual(notice(), "");
    calculate(dom);
    assert.equal(notice(), "");
    // パターンの選択の変更も入力の変更として扱う。
    $(dom, ".pattern-block input[type=checkbox]:checked").click();
    assert.notEqual(notice(), "");

    // 注意はタブごとに判定する。計算済みの2つのタブの片方だけを変える。
    $(dom, ".pattern-block input[type=checkbox]:not(:checked)").click();
    calculate(dom);
    $(dom, "#addTabBtn").click();
    calculate(dom);
    setValue(dom, $(dom, "#buffer"), "50");
    assert.notEqual(notice(), "");
    clickTab(dom, 0);
    assert.equal(notice(), "");
    clickTab(dom, 1);
    assert.notEqual(notice(), "");
  });

  test("計算できなかった後も、残した参考結果の入力と違えば注意を表示し続ける（SIEGE-043、SIEGE-034）", t => {
    const dom = openSiege();
    t.after(() => dom.window.close());
    const notice = () => $(dom, "#resultNotice").textContent;
    const previous = run(EXAMPLE_1, dom);
    $(dom, ".role-select").value = "削り";
    $(dom, ".role-select").dispatchEvent(new dom.window.Event("change", { bubbles: true }));
    assert.notEqual(notice(), "");

    const { output, reference } = calculate(dom);
    assert.equal(output, "メイン役割のメンバーがいません");
    assert.equal(reference, previous.reference);
    assert.equal(notice(), "⚠ 参考：2周分の計算結果は、変更前の入力で計算したものです");
    // 開き直しても、引き継いだ入力と比べて同じ注意を出す。
    const reopened = openSiege({ storage: storageOf(dom) });
    t.after(() => reopened.window.close());
    assert.equal($(reopened, "#resultNotice").textContent, "⚠ 参考：2周分の計算結果は、変更前の入力で計算したものです");
    assert.equal($(reopened, "#refOutputCard").style.display, "block");
    // 計算できなかった計算を重ねても、参考結果を残し、その入力と比べ続ける。
    assert.equal(calculate(dom).reference, previous.reference);
    assert.equal(savedTabs(dom).tabs[0].result.reference, previous.reference);
    assert.equal(notice(), "⚠ 参考：2周分の計算結果は、変更前の入力で計算したものです");
    // 参考結果の入力へ戻すと注意を消す。
    $(dom, ".role-select").value = "メイン";
    $(dom, ".role-select").dispatchEvent(new dom.window.Event("change", { bubbles: true }));
    assert.equal(notice(), "");
  });

  test("残した参考結果がなければ、計算できなかった後に入力を変えても注意を出さない（SIEGE-043）", t => {
    const dom = openSiege();
    t.after(() => dom.window.close());
    const notice = () => $(dom, "#resultNotice").textContent;
    run({ ...EXAMPLE_1, patterns: [] }, dom);
    assert.equal(notice(), "");
    setValue(dom, $(dom, "#buffer"), "45");
    assert.equal(notice(), "");

    // パターン0件に続けてメイン0人で計算しても、比べる参考結果がないため注意を出さない。
    $(dom, "#addPatternBtn").click();
    $(dom, ".role-select").value = "削り";
    $(dom, ".role-select").dispatchEvent(new dom.window.Event("change", { bubbles: true }));
    assert.equal(calculate(dom).output, "メイン役割のメンバーがいません");
    assert.equal(notice(), "");
    assert.equal(savedTabs(dom).tabs[0].result.inputKey, null);
  });

  test("localStorageを使えなくても計算できる（COM-041）", t => {
    const dom = openSiege();
    t.after(() => dom.window.close());
    dom.window.Storage.prototype.setItem = () => { throw new Error("使えない"); };
    const { output, reference } = run(EXAMPLE_1, dom);
    assert.deepEqual(checkProperties(EXAMPLE_1, output, reference), []);
  });
});
