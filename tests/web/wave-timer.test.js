"use strict";
// 周期ウェーブタイマー（web/周期ウェーブタイマー.html）を実物のまま動かす検査。
// 要件IDはdocs/requirements/web-tools/wave-timer.mdを参照する。
// 予定の追加はsetTimeoutで行われるため、時計（createClock）を進めたときに追加される。
// スタート直後の1個目も、時計を0ミリ秒進めたときに追加される（ブラウザではsetTimeoutの0ミリ秒後）。

const test = require("node:test");
const assert = require("node:assert/strict");
const {
  createClock, openSiege, openWave, storageOf, readJson, setValue, $, $$, fillSiege, calculate,
  STORAGE_FAILURES,
} = require("./helpers");

const SIEGE_KEY = "siegeTimelineForWaveTimer";

function open(t, options) {
  const dom = openWave(options);
  t.after(() => dom.window.close());
  return dom;
}

// 表示中のタブで計測を始め、1個目の予定を追加する。
function start(dom, clock) {
  $(dom, "#startBtn").click();
  clock.advance(0);
}

// 予定のカードごとに、番号、経過時間、進行中のパターン、上の「⏱」、下の「⚠」とボタンを返す。
function stack(dom) {
  const entries = [];
  let upcoming = [];
  for (const el of $(dom, "#itemStack").children) {
    if (el.classList.contains("upcoming-launch")) {
      upcoming = Array.from(el.querySelectorAll(".upcoming-item")).map(e => e.textContent);
    } else if (el.classList.contains("item-card")) {
      const timeline = el.querySelector(".item-timeline");
      entries.push({
        label: el.querySelector(".item-label").textContent,
        num: el.querySelector(".item-num").textContent,
        timeline: timeline
          ? Array.from(timeline.children).map(e => e.textContent)
          : null,
        upcoming,
        missed: [],
      });
      upcoming = [];
    } else if (el.classList.contains("missed-launch")) {
      entries[entries.length - 1].missed = Array.from(el.querySelectorAll(".missed-item")).map(item => ({
        text: item.querySelector(".missed-label").textContent,
        buttons: Array.from(item.querySelectorAll(".alt-btn")).map(b => b.textContent),
      }));
    }
  }
  return entries;
}

const nums = dom => stack(dom).map(e => e.num);

function paste(dom, text) {
  setValue(dom, $(dom, "#pasteBox"), text);
}

function setSettings(dom, values) {
  Object.entries(values).forEach(([id, value]) => setValue(dom, $(dom, "#" + id), value));
}

const tabTitles = dom => $$(dom, "#tabBar .tab-title-input").map(input => input.value);
const currentTitle = dom => $(dom, "#tabBar .tab-item.active .tab-title-input").value;
const clickTab = (dom, index) => $$(dom, "#tabBar .tab-title-input")[index].click();
const addTab = dom => $(dom, "#tabBar .tab-add").click();
const closeButtons = dom => $$(dom, "#tabBar .tab-close");

// 別のブラウザのタブで集結タイムライン計算が保存したときと同じ通知を送る。
function receiveSiege(dom, data) {
  const value = JSON.stringify(data);
  dom.window.localStorage.setItem(SIEGE_KEY, value);
  dom.window.dispatchEvent(new dom.window.StorageEvent("storage", { key: SIEGE_KEY, newValue: value }));
}

// 集結タイムライン計算の実物で計算した結果を保存データごと返す（SIEGE-045）。
// 削りの集結5分、メイン／増援の集結3分。周期660秒、1周目の帰還の最大値768秒になる例。
function siegeResult(t) {
  const siege = openSiege();
  t.after(() => siege.window.close());
  fillSiege(siege, {
    settings: { kz: 5, mr: 3, gap: 1, buf: 30 },
    petSame: null,
    members: [
      { role: "メイン", label: "M", march: 60 },
      { role: "増援", label: "R", march: 40 },
      { role: "削り", label: "A", march: 30 },
      { role: "削り", label: "B", march: 100, pet: 8, usePet: true },
      { role: "削り", label: "C", march: 50 },
    ],
    patterns: [{ kezuri: ["A", "B"], reinforce: ["R"] }, { kezuri: ["C"], reinforce: [] }],
  });
  const { output } = calculate(siege);
  const storage = storageOf(siege);
  return { output, storage, raw: storage[SIEGE_KEY], saved: JSON.parse(storage[SIEGE_KEY]) };
}

test.describe("設定（WAVE-001〜WAVE-003）", () => {
  test("既定値は周期10秒、MAX30秒、表示延長3秒", t => {
    const dom = open(t);
    assert.deepEqual(["periodMin", "periodSec", "maxMin", "maxSec", "extraDisplaySec"].map(id => $(dom, "#" + id).value),
      ["0", "10", "0", "30", "3"]);
  });

  test("周期とMAXは分 × 60 + 秒で求め、経過時間はMM:SS.tで切り捨てて表示する（WAVE-002、WAVE-013）", t => {
    const clock = createClock();
    const dom = open(t, { clock });
    setSettings(dom, { periodMin: "1", periodSec: "5", maxMin: "2", maxSec: "0" });
    start(dom, clock);
    clock.advance(1299);
    assert.deepEqual(nums(dom), ["00:01.2"]);
    clock.advance(65000 - 1299 - 1);
    assert.deepEqual(nums(dom), ["01:04.9"]);
    clock.advance(1);
    assert.deepEqual(nums(dom), ["01:05.0", "00:00.0"]);
    assert.deepEqual(stack(dom).map(e => e.label), ["1個目", "2個目"]);
  });

  test("1秒未満の周期とMAXは1秒、0秒未満の表示延長は0秒とする（WAVE-002）", t => {
    const clock = createClock();
    const dom = open(t, { clock });
    setSettings(dom, { periodSec: "0", maxSec: "0", extraDisplaySec: "-3" });
    start(dom, clock);
    clock.advance(999);
    assert.deepEqual(nums(dom), ["00:00.9"]);
    // 1個目はMAX1秒 + 表示延長0秒で消え、同時に周期1秒の2個目が加わる。
    clock.advance(1);
    assert.deepEqual(nums(dom), ["00:00.0"]);
  });

  test("計測中は設定を編集できず、ストップ後は編集できる（WAVE-003）", t => {
    const clock = createClock();
    const dom = open(t, { clock });
    const inputs = () => ["periodMin", "periodSec", "maxMin", "maxSec", "extraDisplaySec"].map(id => $(dom, "#" + id).disabled);
    assert.deepEqual(inputs(), [false, false, false, false, false]);
    start(dom, clock);
    assert.deepEqual(inputs(), [true, true, true, true, true]);
    $(dom, "#stopBtn").click();
    assert.deepEqual(inputs(), [false, false, false, false, false]);
  });
});

test.describe("予定の追加と削除、操作（WAVE-010〜WAVE-014、WAVE-020〜WAVE-023）", () => {
  test("周期ごとに予定を追加し、MAX + 表示延長に達した予定を消す", t => {
    const clock = createClock();
    const dom = open(t, { clock });
    assert.equal($(dom, "#emptyMsg").textContent, "まだ予定がありません");
    assert.equal($(dom, "#emptyMsg").style.display, "block");

    start(dom, clock);
    assert.deepEqual(nums(dom), ["00:00.0"]);
    assert.equal($(dom, "#emptyMsg").style.display, "none");
    // ちょうど0.1秒の境目では、浮動小数の誤差で表示が0.1秒少なくなることがあるため、境目を避ける。
    clock.advanceBy(32950);
    assert.deepEqual(nums(dom), ["00:32.9", "00:22.9", "00:12.9", "00:02.9"]);
    assert.deepEqual(stack(dom).map(e => e.label), ["1個目", "2個目", "3個目", "4個目"]);
    clock.advance(50);
    assert.deepEqual(nums(dom), ["00:23.0", "00:13.0", "00:03.0"]);
    // 計測中のスタートは無視する（WAVE-020）。
    $(dom, "#startBtn").click();
    clock.advance(0);
    assert.deepEqual(nums(dom), ["00:23.0", "00:13.0", "00:03.0"]);
  });

  test("タブの休止などで遅れても、予定の時刻はスタート時刻からの絶対時刻で決める（WAVE-011）", t => {
    const clock = createClock();
    const dom = open(t, { clock });
    start(dom, clock);
    // 25秒間タイマーも描画も止まり、まとめて実行された場合。
    clock.advance(25000);
    assert.deepEqual(nums(dom), ["00:25.0", "00:15.0", "00:05.0"]);
  });

  test("ストップで凍結し、スタートで最初から計測し、リセットで消す（WAVE-021〜WAVE-023）", t => {
    const clock = createClock();
    const dom = open(t, { clock });
    paste(dom, "0分30秒 → ①A（5分集結）");
    start(dom, clock);
    clock.advanceBy(12300);
    const before = stack(dom);
    assert.deepEqual(before.map(e => e.num), ["00:12.3", "00:02.3"]);
    assert.deepEqual(before.map(e => e.upcoming), [["⏱ 18秒後：①A"], ["⏱ 28秒後：①A"]]);

    $(dom, "#stopBtn").click();
    assert.equal($(dom, "#stopBtn").disabled, true);
    assert.equal($(dom, "#startBtn").disabled, false);
    clock.advanceBy(20000);
    assert.deepEqual(stack(dom), before);

    $(dom, "#startBtn").click();
    clock.advance(0);
    assert.deepEqual(nums(dom), ["00:00.0"]);
    clock.advanceBy(5000);
    assert.deepEqual(nums(dom), ["00:05.0"]);

    $(dom, "#resetBtn").click();
    assert.deepEqual(stack(dom), []);
    assert.equal($(dom, "#emptyMsg").style.display, "block");
    assert.equal($(dom, "#startBtn").disabled, false);
    assert.equal($(dom, "#stopBtn").disabled, true);
    clock.advanceBy(20000);
    assert.deepEqual(stack(dom), []);
  });
});

test.describe("タイムラインの解析と進行表示（WAVE-030〜WAVE-032、WAVE-043〜WAVE-049）", () => {
  const TIMELINE = [
    "①A+B→メイン→増援",
    "0分10秒 → ①B（5分集結）※行軍77秒（6分17秒着、7分34秒帰還）",
    "0:20 → ①A(3分集結)",
    "0分15秒 → ①B（5分集結）",
    "②C→メイン",
    "0分30秒 → ②C（5分集結）",
    "メモ 0分40秒 → ③X（5分集結）",
    "0分50秒 ③Y → 予定",
    "0:45 → 予定なし",
    "1分00秒 → ②D（3分集結）",
    "",
    "周期：11分00秒",
  ].join("\n");

  test("発起行だけを読み、記号ごとに名前を重複なく連結した見出しを1個目のカードに並べる（WAVE-031、WAVE-032、WAVE-045）", t => {
    const clock = createClock();
    const dom = open(t, { clock });
    paste(dom, TIMELINE);
    setSettings(dom, { periodMin: "5", maxMin: "5" });
    start(dom, clock);
    const [first] = stack(dom);
    assert.deepEqual(first.timeline, ["①B+A", "②C+D"]);
    assert.deepEqual(first.upcoming, ["⏱ 10秒後：①B", "⏱ 15秒後：①B", "⏱ 20秒後：①A", "⏱ 30秒後：②C", "⏱ 60秒後：②D"]);
    // パターンの最後の発起（①は20秒、②は60秒）を過ぎたパターンは並べない。
    clock.advance(20000);
    assert.deepEqual(stack(dom)[0].timeline, ["②C+D"]);
    clock.advance(40000);
    assert.deepEqual(stack(dom)[0].timeline, []);
  });

  test("2個目以降のカードにはパターンを並べず、各予定は追加された時刻を0秒として独立に進む（WAVE-044、WAVE-045）", t => {
    const clock = createClock();
    const dom = open(t, { clock });
    paste(dom, TIMELINE);
    start(dom, clock);
    clock.advanceBy(12000);
    const [first, second] = stack(dom);
    assert.deepEqual(first.upcoming, ["⏱ 3秒後：①B", "⏱ 8秒後：①A", "⏱ 18秒後：②C", "⏱ 48秒後：②D"]);
    assert.deepEqual(first.missed.map(m => m.text), ["⚠ 2秒前に発起予定だった：①B"]);
    assert.equal(second.timeline, null);
    assert.deepEqual(second.upcoming, ["⏱ 8秒後：①B", "⏱ 13秒後：①B", "⏱ 18秒後：①A", "⏱ 28秒後：②C", "⏱ 58秒後：②D"]);
    assert.deepEqual(second.missed, []);
  });

  test("発起行が1つもなければ、1個目のカードに貼り付けられていないと表示する（WAVE-043）", t => {
    const clock = createClock();
    const dom = open(t, { clock });
    start(dom, clock);
    assert.deepEqual(stack(dom)[0].timeline, ["タイムラインのテキストが貼り付けられていません"]);
    paste(dom, "①A→メイン\n\n周期：1分00秒");
    assert.deepEqual(stack(dom)[0].timeline, ["タイムラインのテキストが貼り付けられていません"]);
    paste(dom, "0分30秒 → ①A（5分集結）");
    assert.deepEqual(stack(dom)[0].timeline, ["①A"]);
  });

  // 同じ秒にまとめる人は、元の集結時間が同じになるようにする。集結時間の違う人が同じ秒にまとまったときは、
  // 一部の人が表示から消える既知の不具合（KI-WAVE-25）に当たるため、期待値にしない。
  const GROUPS = [
    "0分10秒 → ①A（5分集結）",
    "0分10秒 → ②B（5分集結）",
    "0分11秒 → ①C（1分集結）",
    "0分12秒 → ②D",
    "0分13秒 → ③E（3分集結）",
    "0分14秒 → ④F（10分集結）",
    "1分20秒 → ③G（3分集結）",
  ].join("\n");

  test("60秒以内に発起する人と、発起を過ぎて30秒以内の人を、四捨五入した秒ごとにまとめる（WAVE-046〜WAVE-048）", t => {
    const clock = createClock();
    const dom = open(t, { clock });
    paste(dom, GROUPS);
    setSettings(dom, { periodMin: "1", periodSec: "40", maxMin: "3", maxSec: "0" });
    start(dom, clock);
    clock.advance(9400);
    assert.deepEqual(stack(dom)[0].upcoming,
      ["⏱ 1秒後：①A、②B", "⏱ 2秒後：①C", "⏱ 3秒後：②D", "⏱ 4秒後：③E", "⏱ 5秒後：④F"]);

    clock.advance(5200); // 経過14.6秒
    const [first] = stack(dom);
    assert.deepEqual(first.upcoming, []);
    // 時短の候補は元の集結時間より短い最大のもの。秒は 発起時刻 + (元 - 候補) × 60 - 経過 を四捨五入する。
    assert.deepEqual(first.missed, [
      { text: "⚠ 1秒前に発起予定だった：④F", buttons: ["5分集結で出す（299秒後）"] },
      { text: "⚠ 2秒前に発起予定だった：③E", buttons: ["1分集結で出す（118秒後）"] },
      { text: "⚠ 3秒前に発起予定だった：②D", buttons: [] },
      { text: "⚠ 4秒前に発起予定だった：①C", buttons: [] },
      { text: "⚠ 5秒前に発起予定だった：①A、②B", buttons: ["3分集結で出す（115秒後）"] },
    ]);

    // 発起を過ぎて30秒までは表示し、それを過ぎたら消す。
    clock.advance(29400); // 経過44.0秒
    assert.deepEqual(stack(dom)[0].missed.map(m => m.text), ["⚠ 30秒前に発起予定だった：④F"]);
    clock.advance(600);
    assert.deepEqual(stack(dom)[0].missed, []);
    // 発起まで60秒を超えていた③G（80秒）は、60秒以内になってから表示する。
    assert.deepEqual(stack(dom)[0].upcoming, ["⏱ 35秒後：③G"]);
  });

  test("時短のボタンを押した人は、その予定でだけ新しい発起時刻と集結時間で扱う（WAVE-049）", t => {
    const clock = createClock();
    const dom = open(t, { clock });
    paste(dom, GROUPS);
    setSettings(dom, { periodMin: "1", periodSec: "40", maxMin: "3", maxSec: "0" });
    start(dom, clock);
    clock.advance(14600);
    const button = $$(dom, ".alt-btn").find(b => b.textContent === "3分集結で出す（115秒後）");
    button.click();
    const [first] = stack(dom);
    assert.deepEqual(first.missed.map(m => m.text), [
      "⚠ 1秒前に発起予定だった：④F", "⚠ 2秒前に発起予定だった：③E",
      "⚠ 3秒前に発起予定だった：②D", "⚠ 4秒前に発起予定だった：①C",
    ]);
    // 新しい発起時刻は 10 + (5 - 3) × 60 = 130秒。経過75秒で残り55秒になる。
    clock.advance(60400);
    assert.deepEqual(stack(dom)[0].upcoming, ["⏱ 5秒後：③G", "⏱ 55秒後：①A、②B"]);
    // 100秒に追加した2個目の予定には適用しない。経過114.6秒で2個目は14.6秒。
    clock.advance(39600);
    const [after, second] = stack(dom);
    assert.deepEqual(after.upcoming, ["⏱ 15秒後：①A、②B"]);
    assert.deepEqual(second.missed.pop(), { text: "⚠ 5秒前に発起予定だった：①A、②B", buttons: ["3分集結で出す（115秒後）"] });
  });

  test("貼り付け欄の入力のたびに保存して解析し、1.5秒間「保存しました」と表示する（WAVE-030）", t => {
    const clock = createClock();
    const dom = open(t, { clock });
    start(dom, clock);
    paste(dom, "0分30秒 → ①A（5分集結）");
    assert.equal(dom.window.localStorage.getItem("waveTimerPastedTimeline"), "0分30秒 → ①A（5分集結）");
    assert.equal($(dom, "#saveStatus").textContent, "保存しました");
    assert.deepEqual(stack(dom)[0].upcoming, ["⏱ 30秒後：①A"]);
    clock.advance(1499);
    assert.equal($(dom, "#saveStatus").textContent, "保存しました");
    clock.advance(1);
    assert.equal($(dom, "#saveStatus").textContent.trim(), "");
  });

  test("保存に失敗したら「この環境では保存できません」と表示する（WAVE-030）", t => {
    const dom = open(t);
    dom.window.Storage.prototype.setItem = () => { throw new dom.window.DOMException("quota", "QuotaExceededError"); };
    paste(dom, "0分30秒 → ①A（5分集結）");
    assert.equal($(dom, "#saveStatus").textContent, "この環境では保存できません");
  });
});

test.describe("localStorageを使えない環境（COM-041）", () => {
  for (const [name, failure] of Object.entries(STORAGE_FAILURES)) {
    test(`保存できなくても、解析、計測、タブの追加ができる（${name}）`, t => {
      const clock = createClock();
      const dom = open(t, { clock, beforeParse: failure });
      paste(dom, "0分30秒 → ①A（5分集結）");
      assert.equal($(dom, "#saveStatus").textContent, "この環境では保存できません");
      start(dom, clock);
      assert.deepEqual(nums(dom), ["00:00.0"]);
      assert.deepEqual(stack(dom)[0].upcoming, ["⏱ 30秒後：①A"]);
      clock.advance(10000);
      assert.deepEqual(nums(dom), ["00:10.0", "00:00.0"]);
      $(dom, "#stopBtn").click();
      addTab(dom);
      assert.deepEqual(tabTitles(dom), ["タイマー1", "タイマー2"]);
      assert.equal(currentTitle(dom), "タイマー2");
    });
  }
});

test.describe("タブ（WAVE-037、WAVE-060〜WAVE-067）", () => {
  test("「+」で既定値と空のタイムラインのタブを末尾に追加して表示し、設定はタブごとに独立する（WAVE-060、WAVE-063）", t => {
    const dom = open(t);
    assert.deepEqual(tabTitles(dom), ["タイマー1"]);
    setSettings(dom, { periodSec: "20" });
    paste(dom, "0分30秒 → ①A（5分集結）");
    addTab(dom);
    assert.deepEqual(tabTitles(dom), ["タイマー1", "タイマー2"]);
    assert.equal(currentTitle(dom), "タイマー2");
    assert.equal($(dom, "#periodSec").value, "10");
    assert.equal($(dom, "#pasteBox").value, "");
    setSettings(dom, { maxSec: "45" });
    addTab(dom);
    assert.deepEqual(tabTitles(dom), ["タイマー1", "タイマー2", "タイマー3"]);
    clickTab(dom, 0);
    assert.equal(currentTitle(dom), "タイマー1");
    assert.equal($(dom, "#periodSec").value, "20");
    assert.equal($(dom, "#maxSec").value, "30");
    assert.equal($(dom, "#pasteBox").value, "0分30秒 → ①A（5分集結）");
    clickTab(dom, 1);
    assert.equal($(dom, "#maxSec").value, "45");
  });

  test("タブの名前を欄で直接変更して保存する（WAVE-064、WAVE-050）", t => {
    const dom = open(t);
    addTab(dom);
    setValue(dom, $$(dom, "#tabBar .tab-title-input")[1], "別動隊");
    assert.deepEqual(readJson(dom, "waveTimerTabs").map(tab => tab.title), ["タイマー1", "別動隊"]);
    const reopened = open(t, { storage: storageOf(dom) });
    assert.deepEqual(tabTitles(reopened), ["タイマー1", "別動隊"]);
    assert.equal(currentTitle(reopened), "別動隊");
  });

  test("「×」は確認を取ってからタブと保存した内容を削除し、取り消せば何も変えない（WAVE-065）", t => {
    let answer = false;
    const messages = [];
    const dom = open(t, { confirm: message => { messages.push(message); return answer; } });
    assert.equal(closeButtons(dom).length, 0);
    addTab(dom);
    setSettings(dom, { periodSec: "20" });
    paste(dom, "0分30秒 → ①A（5分集結）");
    $(dom, "#hideSideBtn").click();
    const id = readJson(dom, "waveTimerTabs")[1].id;
    addTab(dom);
    assert.equal(closeButtons(dom).length, 3);
    const keys = ["waveTimerSettings_", "waveTimerPastedTimeline_", "waveTimerSideHidden_"].map(k => k + id);
    assert.ok(keys.every(key => dom.window.localStorage.getItem(key) !== null));

    closeButtons(dom)[1].click();
    assert.equal(messages.length, 1);
    assert.deepEqual(tabTitles(dom), ["タイマー1", "タイマー2", "タイマー3"]);
    assert.ok(keys.every(key => dom.window.localStorage.getItem(key) !== null));

    // 表示していないタブを削除しても、表示中のタブは変えない。
    answer = true;
    closeButtons(dom)[1].click();
    assert.deepEqual(tabTitles(dom), ["タイマー1", "タイマー3"]);
    assert.equal(currentTitle(dom), "タイマー3");
    assert.ok(keys.every(key => dom.window.localStorage.getItem(key) === null));
    assert.deepEqual(readJson(dom, "waveTimerTabs").map(tab => tab.title), ["タイマー1", "タイマー3"]);

    // 表示中のタブを削除すると、先頭のタブを表示する。1つだけになれば「×」を出さない。
    closeButtons(dom)[1].click();
    assert.deepEqual(tabTitles(dom), ["タイマー1"]);
    assert.equal(currentTitle(dom), "タイマー1");
    assert.equal(closeButtons(dom).length, 0);
    assert.equal(dom.window.localStorage.getItem("waveTimerCurrentTab"), "default");
  });

  test("表示中のタブを削除して先頭のタブを表示する場合も、先頭のタブの設定を表示する（WAVE-065）", t => {
    const dom = open(t);
    setSettings(dom, { periodSec: "25" });
    addTab(dom);
    addTab(dom);
    clickTab(dom, 1);
    closeButtons(dom)[1].click();
    assert.deepEqual(tabTitles(dom), ["タイマー1", "タイマー3"]);
    assert.equal(currentTitle(dom), "タイマー1");
    assert.equal($(dom, "#periodSec").value, "25");
  });

  test("計測中かストップ後に切り替えるときは確認し、取り消せば切り替えず、切り替えれば計測を終える（WAVE-060、WAVE-067）", t => {
    const clock = createClock();
    let answer = false;
    const messages = [];
    const dom = open(t, { clock, confirm: message => { messages.push(message); return answer; } });
    addTab(dom);
    clickTab(dom, 0);
    // 計測していなければ確認しない。
    assert.deepEqual(messages, []);

    start(dom, clock);
    clock.advanceBy(1000);
    clickTab(dom, 1);
    assert.deepEqual(messages, ["動いているタイマーを止めてタブを切り替えます。よろしいですか？"]);
    assert.equal(currentTitle(dom), "タイマー1");
    assert.equal($(dom, "#startBtn").disabled, true);
    clock.advanceBy(1000);
    assert.deepEqual(nums(dom), ["00:02.0"]);

    $(dom, "#stopBtn").click();
    clickTab(dom, 1);
    assert.equal(messages.length, 2);
    assert.equal(currentTitle(dom), "タイマー1");

    answer = true;
    clickTab(dom, 1);
    assert.equal(messages.length, 3);
    assert.equal(currentTitle(dom), "タイマー2");
    assert.deepEqual(stack(dom), []);
    assert.equal($(dom, "#startBtn").disabled, false);
    // 切り替えた後は計測していないため、戻るときは確認しない。計測も終わっている。
    clickTab(dom, 0);
    assert.equal(messages.length, 3);
    clock.advanceBy(1000);
    assert.deepEqual(stack(dom), []);
  });

  test("計測中にタブを追加するときも確認し、追加したタブへ切り替えると計測を終える（WAVE-067）", t => {
    // 確認を取り消した場合はKI-WAVE-22に当たるため確かめない。
    const clock = createClock();
    const messages = [];
    const dom = open(t, { clock, confirm: message => { messages.push(message); return true; } });
    start(dom, clock);
    addTab(dom);
    assert.equal(messages.length, 1);
    assert.equal(currentTitle(dom), "タイマー2");
    clock.advanceBy(1000);
    assert.deepEqual(stack(dom), []);
  });

  test("貼り付け欄を隠して表示を戻せ、その状態をタブごとに保存する（WAVE-037、WAVE-051）", t => {
    const dom = open(t);
    const side = () => [$(dom, "#colSide").style.display, $(dom, "#hideSideBtn").textContent];
    assert.deepEqual(side(), ["", "貼り付け欄を隠す"]);
    $(dom, "#hideSideBtn").click();
    assert.deepEqual(side(), ["none", "貼り付け欄を表示"]);
    assert.equal(dom.window.localStorage.getItem("waveTimerSideHidden"), "1");
    addTab(dom);
    assert.deepEqual(side(), ["", "貼り付け欄を隠す"]);
    clickTab(dom, 0);
    assert.deepEqual(side(), ["none", "貼り付け欄を表示"]);
    $(dom, "#hideSideBtn").click();
    assert.equal(dom.window.localStorage.getItem("waveTimerSideHidden"), "0");
  });
});

test.describe("保存（WAVE-050〜WAVE-052）", () => {
  test("タブの一覧、最後に表示したタブ、タブごとの設定とタイムラインを保存して復元し、計測は停止している", t => {
    const clock = createClock();
    const dom = open(t, { clock });
    setSettings(dom, { periodMin: "1", periodSec: "5", maxMin: "2", maxSec: "15", extraDisplaySec: "4" });
    paste(dom, "0分30秒 → ①A（5分集結）");
    addTab(dom);
    setSettings(dom, { periodSec: "20" });
    paste(dom, "0分40秒 → ②B（3分集結）");
    $(dom, "#hideSideBtn").click();
    start(dom, clock);

    const tabs = readJson(dom, "waveTimerTabs");
    assert.deepEqual(tabs.map(tab => tab.title), ["タイマー1", "タイマー2"]);
    assert.deepEqual(tabs.map(tab => Object.keys(tab).sort()), [["id", "title"], ["id", "title"]]);
    assert.equal(tabs[0].id, "default");
    const id = tabs[1].id;
    assert.equal(dom.window.localStorage.getItem("waveTimerCurrentTab"), id);
    // 最初のタブは接尾辞のないキー、追加したタブは`_{id}`を付けたキーを使う（WAVE-051、WAVE-052）。
    assert.deepEqual(readJson(dom, "waveTimerSettings"),
      { periodMin: "1", periodSec: "5", maxMin: "2", maxSec: "15", extraDisplaySec: "4" });
    assert.deepEqual(readJson(dom, "waveTimerSettings_" + id),
      { periodMin: "0", periodSec: "20", maxMin: "0", maxSec: "30", extraDisplaySec: "3" });
    assert.equal(dom.window.localStorage.getItem("waveTimerPastedTimeline"), "0分30秒 → ①A（5分集結）");
    assert.equal(dom.window.localStorage.getItem("waveTimerPastedTimeline_" + id), "0分40秒 → ②B（3分集結）");
    assert.equal(dom.window.localStorage.getItem("waveTimerSideHidden_" + id), "1");
    assert.equal(dom.window.localStorage.getItem("waveTimerSideHidden"), null);

    const clock2 = createClock();
    const reopened = open(t, { clock: clock2, storage: storageOf(dom) });
    assert.deepEqual(tabTitles(reopened), ["タイマー1", "タイマー2"]);
    assert.equal(currentTitle(reopened), "タイマー2");
    assert.equal($(reopened, "#periodSec").value, "20");
    assert.equal($(reopened, "#pasteBox").value, "0分40秒 → ②B（3分集結）");
    assert.equal($(reopened, "#colSide").style.display, "none");
    assert.equal($(reopened, "#startBtn").disabled, false);
    clock2.advanceBy(1000);
    assert.deepEqual(stack(reopened), []);
    clickTab(reopened, 0);
    assert.deepEqual(["periodMin", "periodSec", "maxMin", "maxSec", "extraDisplaySec"].map(i => $(reopened, "#" + i).value),
      ["1", "5", "2", "15", "4"]);
    assert.equal($(reopened, "#pasteBox").value, "0分30秒 → ①A（5分集結）");
    assert.equal($(reopened, "#colSide").style.display, "");
  });

  test("タブの一覧がなければ、接尾辞のないキーの設定とタイムラインを最初のタブ「タイマー1」に表示する（WAVE-052）", t => {
    const legacy = {
      waveTimerSettings: JSON.stringify({ periodMin: "2", periodSec: "30", maxMin: "4", maxSec: "0", extraDisplaySec: "5" }),
      waveTimerPastedTimeline: "0分30秒 → ①A（5分集結）",
      waveTimerSideHidden: "1",
    };
    for (const tabs of [undefined, "[]", "{}", "\"default\"", "{壊れたJSON"]) {
      const storage = tabs === undefined ? legacy : { ...legacy, waveTimerTabs: tabs };
      const dom = open(t, { storage });
      assert.deepEqual(tabTitles(dom), ["タイマー1"], String(tabs));
      assert.equal($(dom, "#periodMin").value, "2");
      assert.equal($(dom, "#periodSec").value, "30");
      assert.equal($(dom, "#maxMin").value, "4");
      assert.equal($(dom, "#pasteBox").value, "0分30秒 → ①A（5分集結）");
      assert.equal($(dom, "#colSide").style.display, "none");
    }
  });

  test("最後に表示していたタブが一覧になければ、最初のタブを表示する（WAVE-050）", t => {
    const dom = open(t, { storage: {
      waveTimerTabs: JSON.stringify([{ id: "default", title: "タイマー1" }, { id: "t1", title: "夜" }]),
      waveTimerCurrentTab: "t9",
      waveTimerSettings_t1: JSON.stringify({ periodSec: "20" }),
    } });
    assert.deepEqual(tabTitles(dom), ["タイマー1", "夜"]);
    assert.equal(currentTitle(dom), "タイマー1");
    clickTab(dom, 1);
    assert.equal($(dom, "#periodSec").value, "20");
  });

  test("設定は入力のたびに保存する（WAVE-051）", t => {
    const dom = open(t);
    setValue(dom, $(dom, "#maxMin"), "7");
    assert.deepEqual(readJson(dom, "waveTimerSettings"),
      { periodMin: "0", periodSec: "10", maxMin: "7", maxSec: "30", extraDisplaySec: "3" });
  });
});

test.describe("集結タイムライン計算からの自動取り込み（WAVE-080〜WAVE-082）", () => {
  test("ページを開くと計算結果を表示中のタブへ取り込み、保存して解析する（WAVE-080、WAVE-081、SIEGE-045）", t => {
    const { output, storage, raw } = siegeResult(t);
    const clock = createClock();
    const dom = open(t, { clock, storage });
    // 周期660秒は11分0秒、MAX768秒は12分48秒。
    assert.deepEqual(["periodMin", "periodSec", "maxMin", "maxSec"].map(id => $(dom, "#" + id).value), ["11", "0", "12", "48"]);
    assert.equal($(dom, "#pasteBox").value, output);
    assert.equal(dom.window.localStorage.getItem("waveTimerPastedTimeline"), output);
    assert.deepEqual(readJson(dom, "waveTimerSettings"),
      { periodMin: "11", periodSec: "0", maxMin: "12", maxSec: "48", extraDisplaySec: "3" });
    assert.equal($(dom, "#saveStatus").textContent, "集結タイムライン計算の結果を自動取得しました");
    clock.advance(2499);
    assert.equal($(dom, "#saveStatus").textContent, "集結タイムライン計算の結果を自動取得しました");
    clock.advance(1);
    assert.equal($(dom, "#saveStatus").textContent.trim(), "");

    // 取り込んだ1周目を解析する。①はB、A、M、Rの順に発起し、Bは0秒、Aは47秒に発起する。
    start(dom, clock);
    clock.advance(1000);
    const [first] = stack(dom);
    assert.deepEqual(first.timeline, ["①B+A+M+R", "②C+M"]);
    assert.deepEqual(first.upcoming, ["⏱ 46秒後：①A"]);
    assert.deepEqual(first.missed, [{ text: "⚠ 1秒前に発起予定だった：①B", buttons: ["3分集結で出す（119秒後）"] }]);
    // 集結タイムライン計算の保存データは書き換えない（WAVE-082）。
    assert.equal(dom.window.localStorage.getItem(SIEGE_KEY), raw);
  });

  test("別のブラウザのタブで保存されたら取り込み、同じ結果は2度取り込まず、計測中は取り込まない（WAVE-080）", t => {
    const { output, saved } = siegeResult(t);
    const clock = createClock();
    const dom = open(t, { clock });
    assert.equal($(dom, "#pasteBox").value, "");

    receiveSiege(dom, saved);
    assert.equal($(dom, "#pasteBox").value, output);
    assert.equal($(dom, "#periodMin").value, "11");

    // 同じ結果の通知では、手で変えた内容を上書きしない。
    paste(dom, "0分30秒 → ①A（5分集結）");
    receiveSiege(dom, saved);
    assert.equal($(dom, "#pasteBox").value, "0分30秒 → ①A（5分集結）");

    // 計測中は取り込まない。
    start(dom, clock);
    receiveSiege(dom, { ...saved, savedAt: saved.savedAt + 1, rawText: "1分00秒 → ②B（3分集結）" });
    assert.equal($(dom, "#pasteBox").value, "0分30秒 → ①A（5分集結）");
    assert.equal($(dom, "#periodMin").value, "11");

    // 他のキーの通知では取り込まない。
    $(dom, "#resetBtn").click();
    dom.window.dispatchEvent(new dom.window.StorageEvent("storage", { key: "waveTimerTabs", newValue: "[]" }));
    assert.equal($(dom, "#pasteBox").value, "0分30秒 → ①A（5分集結）");

    receiveSiege(dom, { ...saved, savedAt: saved.savedAt + 2, rawText: "1分00秒 → ②B（3分集結）" });
    assert.equal($(dom, "#pasteBox").value, "1分00秒 → ②B（3分集結）");
    assert.equal(dom.window.localStorage.getItem("waveTimerPastedTimeline"), "1分00秒 → ②B（3分集結）");
  });

  test("周期とMAXは正の数のときだけ、タイムラインは空でないときだけ入れる（WAVE-081）", t => {
    const dom = open(t);
    setSettings(dom, { periodMin: "1", periodSec: "2", maxMin: "3", maxSec: "4" });
    paste(dom, "0分30秒 → ①A（5分集結）");
    const keep = () => assert.deepEqual(
      [...["periodMin", "periodSec", "maxMin", "maxSec"].map(id => $(dom, "#" + id).value), $(dom, "#pasteBox").value],
      ["1", "2", "3", "4", "0分30秒 → ①A（5分集結）"]);
    receiveSiege(dom, { savedAt: 1, periodSec: 0, maxSec: null, rawText: "" });
    keep();
    assert.equal($(dom, "#saveStatus").textContent, "集結タイムライン計算の結果を自動取得しました");
    receiveSiege(dom, { savedAt: 2, periodSec: -5, maxSec: 0 });
    keep();
    receiveSiege(dom, { savedAt: 3, periodSec: "90", maxSec: "120", rawText: 5 });
    keep();
    receiveSiege(dom, { savedAt: 4, periodSec: 125, maxSec: 59 });
    assert.deepEqual(["periodMin", "periodSec", "maxMin", "maxSec"].map(id => $(dom, "#" + id).value), ["2", "5", "0", "59"]);
    assert.equal($(dom, "#pasteBox").value, "0分30秒 → ①A（5分集結）");
  });

  test("追加したタブを表示していれば、そのタブへ取り込む（WAVE-080、WAVE-051）", t => {
    const { output, saved } = siegeResult(t);
    const dom = open(t);
    addTab(dom);
    const id = readJson(dom, "waveTimerTabs")[1].id;
    receiveSiege(dom, saved);
    assert.equal(dom.window.localStorage.getItem("waveTimerPastedTimeline_" + id), output);
    assert.equal(readJson(dom, "waveTimerSettings_" + id).periodMin, "11");
    assert.equal(dom.window.localStorage.getItem("waveTimerPastedTimeline"), null);
    clickTab(dom, 0);
    assert.equal($(dom, "#pasteBox").value, "");
  });
});
