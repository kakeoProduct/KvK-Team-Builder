"use strict";
// 周期ウェーブタイマー（web/周期ウェーブタイマー.html）を実物のまま動かす検査。
// 要件IDはdocs/requirements/web-tools/wave-timer.mdを参照する。

const test = require("node:test");
const assert = require("node:assert/strict");
const {
  createClock, openSiege, openWave, storageOf, setValue, $, $$, tabs, selectedTab, clickTab,
  fillSiege, calculate,
} = require("./helpers");

const SIEGE_CASE = {
  settings: { kz: 5, mr: 3, gap: 1, buf: 30 },
  members: [
    ["メイン", "M", 10], ["増援", "R", 10],
    ["削り", "A", 30], ["削り", "B", 20], ["削り", "C", 10],
    ["削り", "D", 5], ["削り", "E", 15], ["削り", "F", 25],
  ],
  patterns: [["A", "B", "C"], ["D"], ["E", "F"]],
};

// 集結タイムライン計算を実物で動かし、計算1を計算済み、計算2を未計算にした保存データを作る。
function siegeStorage(t) {
  const siege = openSiege();
  t.after(() => siege.window.close());
  fillSiege(siege, SIEGE_CASE);
  const { output } = calculate(siege);
  $(siege, "#addTabBtn").click();
  return { siege, output, storage: storageOf(siege) };
}

function cardNumbers(dom) {
  return $$(dom, "#itemStack .item-num").map(el => el.textContent);
}

// 別のブラウザのタブで集結タイムライン計算が保存したときと同じ通知を送る。
function receiveSiegeUpdate(wave, siege) {
  const value = siege.window.localStorage.getItem("siegeCalcTabs");
  wave.window.localStorage.setItem("siegeCalcTabs", value);
  wave.window.dispatchEvent(new wave.window.StorageEvent("storage", { key: "siegeCalcTabs", newValue: value }));
}

test.describe("タブと計測（WAVE-060〜WAVE-066）", () => {
  test("2つのタブを同時に計測し、表示していないタブの経過時間も進む", t => {
    const clock = createClock();
    const dom = openWave({ clock });
    t.after(() => dom.window.close());

    $(dom, "#startBtn").click();
    clock.advance(5000);
    $(dom, "#addTabBtn").click();
    assert.deepEqual(tabs(dom).map(tab => tab.textContent), ["タイマー1 ▶ 00:05.0", "タイマー2"]);
    // 新しいタブは停止していて、設定を編集できる。
    assert.equal($(dom, "#startBtn").disabled, false);
    assert.equal($(dom, "#periodSec").disabled, false);
    assert.equal($(dom, "#emptyMsg").style.display, "block");

    $(dom, "#startBtn").click();
    clock.advance(3000);
    assert.deepEqual(tabs(dom).map(tab => tab.textContent), ["タイマー1 ▶ 00:08.0", "タイマー2 ▶ 00:03.0"]);
    assert.deepEqual(cardNumbers(dom), ["00:03.0"]);

    clickTab(dom, 0);
    assert.deepEqual(cardNumbers(dom), ["00:08.0"]);
    assert.equal($(dom, "#startBtn").disabled, true);
    assert.equal($(dom, "#periodSec").disabled, true);

    clock.advance(4000);
    // 周期10秒ごとに予定が増える（WAVE-010）。
    assert.deepEqual(cardNumbers(dom), ["00:12.0", "00:02.0"]);

    clickTab(dom, 1);
    $(dom, "#stopBtn").click();
    clock.advance(2000);
    assert.deepEqual(tabs(dom).map(tab => tab.textContent), ["タイマー1 ▶ 00:14.0", "タイマー2"]);
    assert.deepEqual(cardNumbers(dom), ["00:07.0"]);
    clickTab(dom, 0);
    assert.deepEqual(cardNumbers(dom), ["00:14.0", "00:04.0"]);
  });

  test("予定の追加、消去、ストップ、再スタート、リセットは従来どおり（WAVE-010〜WAVE-023）", t => {
    const clock = createClock();
    const dom = openWave({ clock });
    t.after(() => dom.window.close());
    assert.equal($(dom, "#emptyMsg").style.display, "block");

    $(dom, "#startBtn").click();
    assert.deepEqual(cardNumbers(dom), ["00:00.0"]);
    clock.advance(32900);
    assert.deepEqual(cardNumbers(dom), ["00:32.9", "00:22.9", "00:12.9", "00:02.9"]);
    // MAX30秒 + 表示延長3秒に達した予定は消える。
    clock.advance(100);
    assert.deepEqual(cardNumbers(dom), ["00:23.0", "00:13.0", "00:03.0"]);
    // 計測中のスタートは無視する。
    $(dom, "#startBtn").click();
    assert.deepEqual(cardNumbers(dom), ["00:23.0", "00:13.0", "00:03.0"]);

    $(dom, "#stopBtn").click();
    clock.advance(20000);
    assert.deepEqual(cardNumbers(dom), ["00:23.0", "00:13.0", "00:03.0"]);
    assert.equal($(dom, "#periodSec").disabled, false);

    setValue(dom, $(dom, "#periodSec"), "5");
    $(dom, "#startBtn").click();
    assert.deepEqual(cardNumbers(dom), ["00:00.0"]);
    clock.advance(5000);
    assert.deepEqual(cardNumbers(dom), ["00:05.0", "00:00.0"]);

    $(dom, "#resetBtn").click();
    assert.deepEqual(cardNumbers(dom), []);
    assert.equal($(dom, "#emptyMsg").style.display, "block");
    assert.equal(selectedTab(dom).textContent, "タイマー1");
  });

  test("計測中のタブを削除すると計測も終える", t => {
    const clock = createClock();
    const dom = openWave({ clock });
    t.after(() => dom.window.close());
    $(dom, "#addTabBtn").click();
    $(dom, "#startBtn").click();
    clock.advance(1000);
    $(dom, "#deleteTabBtn").click();
    assert.deepEqual(tabs(dom).map(tab => tab.textContent), ["タイマー1"]);
    assert.equal($(dom, "#deleteTabBtn").disabled, true);
    clock.advance(1000);
    assert.deepEqual(tabs(dom).map(tab => tab.textContent), ["タイマー1"]);
  });

  test("設定はタブごとに独立し、名前を変更できる", t => {
    const dom = openWave({ confirm: () => false });
    t.after(() => dom.window.close());
    setValue(dom, $(dom, "#periodSec"), "20");
    $(dom, "#addTabBtn").click();
    assert.equal($(dom, "#periodSec").value, "10");
    setValue(dom, $(dom, "#tabNameInput"), "別動隊");
    assert.deepEqual(tabs(dom).map(tab => tab.textContent), ["タイマー1", "別動隊"]);
    $(dom, "#deleteTabBtn").click();
    assert.equal(tabs(dom).length, 2);
    clickTab(dom, 0);
    assert.equal($(dom, "#periodSec").value, "20");
    setValue(dom, $(dom, "#tabNameInput"), "");
    assert.equal(selectedTab(dom).textContent, "タイマー1");
  });

  test("矢印キーでタブを切り替える", t => {
    const dom = openWave();
    t.after(() => dom.window.close());
    $(dom, "#addTabBtn").click();
    tabs(dom)[1].focus();
    dom.window.document.activeElement.dispatchEvent(
      new dom.window.KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true }));
    assert.equal(selectedTab(dom).textContent, "タイマー1");
    assert.equal(dom.window.document.activeElement, selectedTab(dom));
  });
});

test.describe("計算元の読み込み（WAVE-070〜WAVE-076）", () => {
  test("選んだ計算元の1周目を読み込み、その周期で進行を表示する", t => {
    const { output, storage } = siegeStorage(t);
    const clock = createClock();
    const dom = openWave({ clock, storage });
    t.after(() => dom.window.close());

    const select = $(dom, "#sourceSelect");
    assert.deepEqual(Array.from(select.options).map(o => o.textContent), ["計算1", "計算2（計算結果なし）"]);
    // 画面幅900px以下で隠す貼り付け欄の側に置かない（WAVE-035、WAVE-070）。
    assert.equal(select.closest(".col-side"), null);

    $(dom, "#loadSourceBtn").click();
    assert.equal($(dom, "#pasteBox").value, output);
    assert.equal($(dom, "#sourceStatus").textContent, "計算元：計算1から読み込み済み");

    // 周期：11分30秒（690秒）でループする。300秒では①が終わって次の周を待つ。
    $(dom, "#startBtn").click();
    clock.advance(300000);
    const waiting = $$(dom, "#itemStack .item-card").pop();
    assert.equal(waiting.querySelector(".item-label").textContent, "2周目");
    assert.equal(waiting.querySelector(".item-num").textContent, "-06:30.0");
    clock.advance(400000);
    // 700秒は2周目の10秒目で、①から始まる。
    const first = $(dom, "#itemStack .item-card .item-timeline");
    assert.match(first.textContent, /①A\+B\+C/);
  });

  test("読み込んだ後の計算し直しは取り込まず、更新されたことを表示する", t => {
    const { siege, output, storage } = siegeStorage(t);
    const clock = createClock();
    const dom = openWave({ clock, storage });
    t.after(() => dom.window.close());
    $(dom, "#loadSourceBtn").click();
    $(dom, "#startBtn").click();
    clock.advance(1000);

    // 別のタブ（計算2）を計算しても、計算1から読み込んだタブは更新扱いにしない。
    calculate(siege);
    receiveSiegeUpdate(dom, siege);
    assert.equal($(dom, "#sourceStatus").textContent, "計算元：計算1から読み込み済み");

    const before = { cards: cardNumbers(dom), timeline: $(dom, "#itemStack .item-timeline").textContent };
    clickTab(siege, 0);
    setValue(siege, $(siege, "#buffer"), "60");
    calculate(siege);
    receiveSiegeUpdate(dom, siege);

    assert.equal($(dom, "#sourceStatus").textContent, "⚠ 計算元が更新されています。もう一度読み込むと反映します");
    assert.equal($(dom, "#sourceStatus").classList.contains("warning"), true);
    assert.equal($(dom, "#pasteBox").value, output);
    assert.equal($(dom, "#startBtn").disabled, true);
    // 計測中の表示も変わらない（WAVE-071）。経過300秒で、次の周までの残りは旧い周期690秒から求まる。
    assert.deepEqual({ cards: cardNumbers(dom), timeline: $(dom, "#itemStack .item-timeline").textContent }, before);
    clock.advance(299000);
    const waiting = () => $$(dom, "#itemStack .item-card").pop().querySelector(".item-num").textContent;
    assert.equal(waiting(), "-06:30.0");

    // 計測中に読み込むと、計測を止めずに新しいタイムラインの周期で続ける。
    $(dom, "#loadSourceBtn").click();
    assert.notEqual($(dom, "#pasteBox").value, output);
    assert.equal($(dom, "#sourceStatus").textContent, "計算元：計算1から読み込み済み");
    assert.equal($(dom, "#startBtn").disabled, true);
    const cycle = $(dom, "#pasteBox").value.match(/周期：(\d+)分(\d+)秒/);
    const newCycle = Number(cycle[1]) * 60 + Number(cycle[2]);
    assert.ok(newCycle > 690);
    clock.advance(0);
    const remain = newCycle - 300;
    assert.equal(waiting(), `-${String(Math.floor(remain / 60)).padStart(2, "0")}:${String(remain % 60).padStart(2, "0")}.0`);
  });

  test("計算元の最新の計算が結果を出せなかったら、読み込み済みのタイムラインを使うと表示する", t => {
    const { siege, output, storage } = siegeStorage(t);
    const dom = openWave({ storage });
    t.after(() => dom.window.close());
    $(dom, "#loadSourceBtn").click();

    clickTab(siege, 0);
    $(siege, ".role-select").value = "削り";
    $(siege, ".role-select").dispatchEvent(new siege.window.Event("change", { bubbles: true }));
    assert.equal(calculate(siege).output, "メイン役割のメンバーがいません");
    receiveSiegeUpdate(dom, siege);
    assert.equal($(dom, "#sourceStatus").textContent,
      "⚠ 計算元の最新の計算は結果を出せませんでした。読み込み済みのタイムラインを使っています");
    assert.equal($(dom, "#pasteBox").value, output);
  });

  test("計算元の入力を変えただけでは、最後に計算した結果を読み込む（SIEGE-043）", t => {
    const { siege, output } = siegeStorage(t);
    clickTab(siege, 0);
    setValue(siege, $(siege, "#buffer"), "45");
    assert.notEqual($(siege, "#resultNotice").textContent, "");
    const dom = openWave({ storage: storageOf(siege) });
    t.after(() => dom.window.close());
    $(dom, "#loadSourceBtn").click();
    assert.equal($(dom, "#pasteBox").value, output);
    assert.equal($(dom, "#sourceStatus").textContent, "計算元：計算1から読み込み済み");
  });

  test("計算元のタブが削除されたら、その旨を表示する", t => {
    const { siege, storage } = siegeStorage(t);
    const dom = openWave({ storage });
    t.after(() => dom.window.close());
    $(dom, "#loadSourceBtn").click();

    clickTab(siege, 0);
    $(siege, "#deleteTabBtn").click();
    receiveSiegeUpdate(dom, siege);
    assert.equal($(dom, "#sourceStatus").textContent, "⚠ 計算元のタブ「計算1」は削除されています");
    assert.deepEqual(Array.from($(dom, "#sourceSelect").options).map(o => o.textContent), ["計算2（計算結果なし）"]);
  });

  test("計算元の保存データが作り直されたら、同じ名前と版番号でも削除されたと表示する（WAVE-073、SIEGE-041）", t => {
    const { storage } = siegeStorage(t);
    const dom = openWave({ storage });
    t.after(() => dom.window.close());
    $(dom, "#loadSourceBtn").click();
    assert.equal($(dom, "#sourceStatus").textContent, "計算元：計算1から読み込み済み");

    // 集結タイムライン計算の保存データだけが壊れ、作り直したタブ「計算1」で同じ入力を1回計算する。
    const rebuilt = openSiege({ storage: { siegeCalcTabs: "{壊れたJSON" } });
    t.after(() => rebuilt.window.close());
    fillSiege(rebuilt, SIEGE_CASE);
    calculate(rebuilt);
    // 名前、通し番号、版番号は読み込んだ計算元と同じで、idだけが違う場面にする。
    const before = JSON.parse(storage.siegeCalcTabs).tabs[0];
    const after = JSON.parse(rebuilt.window.localStorage.getItem("siegeCalcTabs")).tabs[0];
    assert.deepEqual([after.name, after.seq, after.result.revision], [before.name, before.seq, before.result.revision]);
    assert.notEqual(after.id, before.id);
    receiveSiegeUpdate(dom, rebuilt);
    assert.equal($(dom, "#sourceStatus").textContent, "⚠ 計算元のタブ「計算1」は削除されています");
  });

  test("集結タイムライン計算を開き直しても、計算元との関連は切れない（SIEGE-041、WAVE-073）", t => {
    const { storage } = siegeStorage(t);
    const dom = openWave({ storage });
    t.after(() => dom.window.close());
    $(dom, "#loadSourceBtn").click();

    // 開き直した集結タイムライン計算で別のタブを計算し、保存し直す。
    const reopened = openSiege({ storage });
    t.after(() => reopened.window.close());
    calculate(reopened);
    receiveSiegeUpdate(dom, reopened);
    assert.equal($(dom, "#sourceStatus").textContent, "計算元：計算1から読み込み済み");
  });

  test("計算元の名前は、読み込み済みでは今の名前、削除では読み込んだ時点の名前を使う（WAVE-073）", t => {
    const { siege, storage } = siegeStorage(t);
    const dom = openWave({ storage });
    t.after(() => dom.window.close());
    $(dom, "#loadSourceBtn").click();

    clickTab(siege, 0);
    setValue(siege, $(siege, "#tabNameInput"), "本隊");
    receiveSiegeUpdate(dom, siege);
    assert.equal($(dom, "#sourceStatus").textContent, "計算元：本隊から読み込み済み");

    $(siege, "#deleteTabBtn").click();
    receiveSiegeUpdate(dom, siege);
    assert.equal($(dom, "#sourceStatus").textContent, "⚠ 計算元のタブ「計算1」は削除されています");
  });

  test("計算し直して読み込める結果の後に読み込めない結果が続けば、結果を出せなかったと表示する（WAVE-073）", t => {
    const { siege, storage } = siegeStorage(t);
    const dom = openWave({ storage });
    t.after(() => dom.window.close());
    $(dom, "#loadSourceBtn").click();

    clickTab(siege, 0);
    setValue(siege, $(siege, "#buffer"), "45");
    calculate(siege);
    receiveSiegeUpdate(dom, siege);
    assert.equal($(dom, "#sourceStatus").textContent, "⚠ 計算元が更新されています。もう一度読み込むと反映します");

    $(siege, ".role-select").value = "削り";
    $(siege, ".role-select").dispatchEvent(new siege.window.Event("change", { bubbles: true }));
    assert.equal(calculate(siege).output, "メイン役割のメンバーがいません");
    receiveSiegeUpdate(dom, siege);
    assert.equal($(dom, "#sourceStatus").textContent,
      "⚠ 計算元の最新の計算は結果を出せませんでした。読み込み済みのタイムラインを使っています");
  });

  test("計算結果のないタブは読み込まない", t => {
    const { storage } = siegeStorage(t);
    const dom = openWave({ storage });
    t.after(() => dom.window.close());
    setValue(dom, $(dom, "#pasteBox"), "①手入力\n0分10秒 → X");
    setValue(dom, $(dom, "#sourceSelect"), $(dom, "#sourceSelect").options[1].value, "change");
    $(dom, "#loadSourceBtn").click();
    assert.equal($(dom, "#sourceStatus").textContent, "このタブには読み込める計算結果がありません");
    assert.equal($(dom, "#pasteBox").value, "①手入力\n0分10秒 → X");
  });

  test("計算元がなければ読み込めないことを示す", t => {
    const dom = openWave();
    t.after(() => dom.window.close());
    const select = $(dom, "#sourceSelect");
    assert.deepEqual(Array.from(select.options).map(o => o.textContent), ["集結タイムライン計算のタブがありません"]);
    assert.equal(select.disabled, true);
    assert.equal($(dom, "#loadSourceBtn").disabled, true);
  });

  test("貼り付け欄を手で編集すると計算元との関連を外す", t => {
    const { storage } = siegeStorage(t);
    const dom = openWave({ storage });
    t.after(() => dom.window.close());
    $(dom, "#loadSourceBtn").click();
    setValue(dom, $(dom, "#pasteBox"), $(dom, "#pasteBox").value + "\n");
    assert.equal($(dom, "#sourceStatus").textContent, "");
    const saved = JSON.parse(dom.window.localStorage.getItem("waveTimerTabs"));
    assert.equal(saved.tabs[0].source, null);
  });

  test("タブごとに別の計算元を持つ", t => {
    const { storage } = siegeStorage(t);
    const dom = openWave({ storage });
    t.after(() => dom.window.close());
    $(dom, "#loadSourceBtn").click();
    $(dom, "#addTabBtn").click();
    assert.equal($(dom, "#pasteBox").value, "");
    assert.equal($(dom, "#sourceStatus").textContent, "");
    clickTab(dom, 0);
    assert.equal($(dom, "#sourceStatus").textContent, "計算元：計算1から読み込み済み");
  });

  test("集結タイムライン計算の保存データを書き換えない（WAVE-076）", t => {
    const { storage } = siegeStorage(t);
    const dom = openWave({ storage });
    t.after(() => dom.window.close());
    $(dom, "#loadSourceBtn").click();
    setValue(dom, $(dom, "#pasteBox"), "書き換え");
    assert.equal(dom.window.localStorage.getItem("siegeCalcTabs"), storage.siegeCalcTabs);
  });
});

test.describe("保存（WAVE-050〜WAVE-053）", () => {
  test("貼り付けの保存に成功すれば知らせ、保存できなくても計測とタブは動く（WAVE-030、COM-041）", t => {
    const clock = createClock();
    const dom = openWave({ clock });
    t.after(() => dom.window.close());
    setValue(dom, $(dom, "#pasteBox"), "①A\n0分00秒 → A\n周期：1分00秒");
    assert.equal($(dom, "#saveStatus").textContent, "保存しました");

    dom.window.Storage.prototype.setItem = () => { throw new Error("使えない"); };
    setValue(dom, $(dom, "#pasteBox"), "①B\n0分00秒 → B\n周期：1分00秒");
    assert.equal($(dom, "#saveStatus").textContent, "この環境では保存できません");

    // 次の周を待つカードを除き、予定のカードだけを見る。
    const firstItem = () => $(dom, "#itemStack .item-card .item-num").textContent;
    $(dom, "#startBtn").click();
    clock.advance(1000);
    assert.equal(firstItem(), "00:01.0");
    $(dom, "#addTabBtn").click();
    assert.deepEqual(tabs(dom).map(tab => tab.textContent), ["タイマー1 ▶ 00:01.0", "タイマー2"]);
    clickTab(dom, 0);
    assert.equal(firstItem(), "00:01.0");
    assert.equal($(dom, "#pasteBox").value, "①B\n0分00秒 → B\n周期：1分00秒");
  });

  test("別のブラウザのタブで保存されたら読み直し、計測中のタブは計測を続ける（WAVE-053）", t => {
    const clock = createClock();
    const a = openWave({ clock: createClock() });
    t.after(() => a.window.close());
    const b = openWave({ clock, storage: storageOf(a) });
    t.after(() => b.window.close());
    $(b, "#startBtn").click();
    clock.advance(5000);

    $(a, "#addTabBtn").click();
    setValue(a, $(a, "#tabNameInput"), "別動隊");
    const value = a.window.localStorage.getItem("waveTimerTabs");
    b.window.localStorage.setItem("waveTimerTabs", value);
    b.window.dispatchEvent(new b.window.StorageEvent("storage", { key: "waveTimerTabs", newValue: value }));

    assert.deepEqual(tabs(b).map(tab => tab.textContent), ["タイマー1 ▶ 00:05.0", "別動隊"]);
    assert.equal(selectedTab(b).textContent, "タイマー1 ▶ 00:05.0");
    clock.advance(1000);
    assert.deepEqual(cardNumbers(b), ["00:06.0"]);
    // Bで設定を変えても、Aで加えたタブは残る。
    clickTab(b, 1);
    setValue(b, $(b, "#periodSec"), "20");
    const saved = JSON.parse(b.window.localStorage.getItem("waveTimerTabs"));
    assert.deepEqual(saved.tabs.map(x => x.name), ["タイマー1", "別動隊"]);
    assert.equal(saved.tabs[1].settings.periodSec, "20");
  });

  function receiveOwnWave(target, source) {
    const value = source.window.localStorage.getItem("waveTimerTabs");
    target.window.localStorage.setItem("waveTimerTabs", value);
    target.window.dispatchEvent(new target.window.StorageEvent("storage", { key: "waveTimerTabs", newValue: value }));
  }

  test("別のブラウザのタブで計測中のタブの設定が変わっても、計測中の設定を表示し続ける（WAVE-053）", t => {
    const clock = createClock();
    const a = openWave({ clock: createClock() });
    t.after(() => a.window.close());
    const b = openWave({ clock, storage: storageOf(a) });
    t.after(() => b.window.close());
    $(b, "#startBtn").click();
    setValue(a, $(a, "#periodSec"), "20");
    setValue(a, $(a, "#pasteBox"), "①A\n0分00秒 → A\n周期：1分00秒");
    receiveOwnWave(b, a);

    // 計測はスタート時の周期10秒で続き、入力欄もその値を表示する。タイムラインは置き換える。
    assert.equal($(b, "#periodSec").value, "10");
    assert.equal($(b, "#periodSec").disabled, true);
    assert.equal($(b, "#pasteBox").value, "①A\n0分00秒 → A\n周期：1分00秒");
    clock.advance(10000);
    assert.deepEqual(cardNumbers(b).slice(0, 2), ["00:10.0", "00:00.0"]);
    // 進行表示も置き換えたタイムラインで続ける（WAVE-071と同じ）。
    const progress = $$(b, "#itemStack .item-timeline").map(el => el.textContent).join(" ");
    assert.match(progress, /①A/);
    assert.doesNotMatch(progress, /貼り付けられていません/);
    // 止めると、保存された設定を表示する。
    $(b, "#stopBtn").click();
    assert.equal($(b, "#periodSec").value, "20");
  });

  test("別のブラウザのタブで計測中のタブが削除されたら、計測を終えたことを知らせる（WAVE-053）", t => {
    const clock = createClock();
    const a = openWave({ clock: createClock() });
    t.after(() => a.window.close());
    $(a, "#addTabBtn").click();
    $(a, "#addTabBtn").click();
    clickTab(a, 1);
    const b = openWave({ clock, storage: storageOf(a) });
    t.after(() => b.window.close());
    $(b, "#startBtn").click();
    clock.advance(1000);

    // Aでタイマー2を削除すると、Aは右隣のタイマー3を表示して保存する。
    $(a, "#deleteTabBtn").click();
    receiveOwnWave(b, a);
    assert.equal($(b, "#externalNotice").textContent, "⚠ 計測中のタブ「タイマー2」は、別のブラウザのタブで削除されたため計測を終えました");
    assert.deepEqual(tabs(b).map(tab => tab.textContent), ["タイマー1", "タイマー3"]);
    assert.equal(selectedTab(b).textContent, "タイマー3");
    // 次に操作すると知らせを消す。
    clickTab(b, 0);
    assert.equal($(b, "#externalNotice").textContent, "");
  });

  test("計測中のタブが続けて削除されたら名前を並べ、タブの追加と削除でも知らせを消す（WAVE-053）", t => {
    const clock = createClock();
    const a = openWave({ clock: createClock() });
    t.after(() => a.window.close());
    $(a, "#addTabBtn").click();
    $(a, "#addTabBtn").click();
    const b = openWave({ clock, storage: storageOf(a) });
    t.after(() => b.window.close());
    // Bはタイマー1とタイマー2を計測し、タイマー3を表示する。
    clickTab(b, 0);
    $(b, "#startBtn").click();
    clickTab(b, 1);
    $(b, "#startBtn").click();
    clickTab(b, 2);

    clickTab(a, 0);
    $(a, "#deleteTabBtn").click();
    receiveOwnWave(b, a);
    // 表示していないタブが消えても、表示中のタブは変わらない。
    assert.equal(selectedTab(b).textContent, "タイマー3");
    clickTab(a, 0);
    $(a, "#deleteTabBtn").click();
    receiveOwnWave(b, a);
    assert.equal($(b, "#externalNotice").textContent,
      "⚠ 計測中のタブ「タイマー1」「タイマー2」は、別のブラウザのタブで削除されたため計測を終えました");

    $(b, "#addTabBtn").click();
    assert.equal($(b, "#externalNotice").textContent, "");

    // 削除でも消す。Bでタブを削除できるよう、Aでタブを2つ加えてから知らせを出す。
    $(a, "#addTabBtn").click();
    $(a, "#addTabBtn").click();
    receiveOwnWave(b, a);
    clickTab(b, 0);
    $(b, "#startBtn").click();
    clickTab(a, 0);
    $(a, "#deleteTabBtn").click();
    receiveOwnWave(b, a);
    assert.notEqual($(b, "#externalNotice").textContent, "");
    $(b, "#deleteTabBtn").click();
    assert.equal($(b, "#externalNotice").textContent, "");
  });

  test("別のブラウザのタブの保存の読み直しでは保存し直さず、読めない保存データは無視する（WAVE-053）", t => {
    const a = openWave();
    t.after(() => a.window.close());
    const b = openWave({ storage: storageOf(a) });
    t.after(() => b.window.close());
    $(a, "#addTabBtn").click();
    let writes = 0;
    const original = b.window.Storage.prototype.setItem;
    b.window.Storage.prototype.setItem = function (...args) { writes += 1; return original.apply(this, args); };
    const value = a.window.localStorage.getItem("waveTimerTabs");
    original.call(b.window.localStorage, "waveTimerTabs", value);
    b.window.dispatchEvent(new b.window.StorageEvent("storage", { key: "waveTimerTabs", newValue: value }));
    assert.equal(writes, 0);
    assert.deepEqual(tabs(b).map(tab => tab.textContent), ["タイマー1", "タイマー2"]);

    for (const broken of [null, "{壊れたJSON", '{"version":1,"tabs":[]}']) {
      if (broken === null) b.window.localStorage.removeItem("waveTimerTabs");
      else original.call(b.window.localStorage, "waveTimerTabs", broken);
      b.window.dispatchEvent(new b.window.StorageEvent("storage", { key: "waveTimerTabs", newValue: broken }));
      assert.deepEqual(tabs(b).map(tab => tab.textContent), ["タイマー1", "タイマー2"], String(broken));
    }
  });

  test("タブのidは、別のブラウザのタブで同時に加えても重ならない（WAVE-051）", t => {
    const a = openWave();
    t.after(() => a.window.close());
    const b = openWave({ storage: storageOf(a) });
    t.after(() => b.window.close());
    $(a, "#addTabBtn").click();
    $(b, "#addTabBtn").click();
    const idA = JSON.parse(a.window.localStorage.getItem("waveTimerTabs")).tabs[1].id;
    const idB = JSON.parse(b.window.localStorage.getItem("waveTimerTabs")).tabs[1].id;
    assert.match(idA, /^w\d+-[0-9a-z]+$/);
    assert.notEqual(idA, idB);
  });

  test("戻る操作でページが復元されたら、離れていた間の保存を読み直す（WAVE-053）", t => {
    const a = openWave();
    t.after(() => a.window.close());
    const b = openWave({ storage: storageOf(a) });
    t.after(() => b.window.close());
    $(a, "#addTabBtn").click();
    b.window.localStorage.setItem("waveTimerTabs", a.window.localStorage.getItem("waveTimerTabs"));
    const shown = new b.window.Event("pageshow");
    Object.defineProperty(shown, "persisted", { value: true });
    b.window.dispatchEvent(shown);
    assert.deepEqual(tabs(b).map(tab => tab.textContent), ["タイマー1", "タイマー2"]);
  });

  test("すべてのタブと最後に表示したタブを保存し、計測は止めて復元する", t => {
    const { storage } = siegeStorage(t);
    const clock = createClock();
    const dom = openWave({ clock, storage });
    t.after(() => dom.window.close());
    $(dom, "#loadSourceBtn").click();
    setValue(dom, $(dom, "#maxSec"), "45");
    $(dom, "#startBtn").click();
    $(dom, "#addTabBtn").click();
    setValue(dom, $(dom, "#tabNameInput"), "予備");
    setValue(dom, $(dom, "#pasteBox"), "①手入力\n0分10秒 → X\n周期：1分00秒");

    const saved = JSON.parse(dom.window.localStorage.getItem("waveTimerTabs"));
    assert.equal(saved.version, 1);
    assert.equal(saved.activeTabId, saved.tabs[1].id);
    assert.equal(saved.tabs[0].settings.maxSec, "45");
    assert.equal(saved.tabs[0].source.siegeTabName, "計算1");
    assert.equal(saved.tabs[0].source.revision, 1);
    assert.equal(saved.tabs[1].timelineText, "①手入力\n0分10秒 → X\n周期：1分00秒");

    const reopened = openWave({ storage: storageOf(dom), clock: createClock() });
    t.after(() => reopened.window.close());
    assert.deepEqual(tabs(reopened).map(tab => tab.textContent), ["タイマー1", "予備"]);
    assert.equal(selectedTab(reopened).textContent, "予備");
    assert.equal($(reopened, "#pasteBox").value, "①手入力\n0分10秒 → X\n周期：1分00秒");
    clickTab(reopened, 0);
    assert.equal($(reopened, "#maxSec").value, "45");
    assert.equal($(reopened, "#startBtn").disabled, false);
    assert.equal($(reopened, "#sourceStatus").textContent, "計算元：計算1から読み込み済み");
  });

  test("旧キーの設定と貼り付けを最初のタブへ移し、旧キーは変えない", t => {
    const settings = JSON.stringify({ periodMin: "1", periodSec: "5", maxMin: "2", maxSec: "0", extraDisplaySec: "7" });
    const pasted = "①旧\n0分00秒 → A\n周期：3分00秒";
    const dom = openWave({ storage: { waveTimerSettings: settings, waveTimerPastedTimeline: pasted } });
    t.after(() => dom.window.close());
    assert.deepEqual(tabs(dom).map(tab => tab.textContent), ["タイマー1"]);
    assert.deepEqual(
      ["periodMin", "periodSec", "maxMin", "maxSec", "extraDisplaySec"].map(id => $(dom, "#" + id).value),
      ["1", "5", "2", "0", "7"]);
    assert.equal($(dom, "#pasteBox").value, pasted);
    setValue(dom, $(dom, "#periodSec"), "9");
    assert.equal(dom.window.localStorage.getItem("waveTimerSettings"), settings);
    assert.equal(dom.window.localStorage.getItem("waveTimerPastedTimeline"), pasted);

    // 移した後に開き直しても、新しいキーを使い、移した後の編集を旧キーで上書きしない。
    const reopened = openWave({ storage: storageOf(dom) });
    t.after(() => reopened.window.close());
    assert.equal(reopened.window.localStorage.getItem("waveTimerSettings"), settings);
    assert.equal($(reopened, "#periodSec").value, "9");
    assert.equal($(reopened, "#pasteBox").value, pasted);
  });

  test("旧形式から移したタイムラインには、計算し直して読み込むよう注意を出す（WAVE-077）", t => {
    const pasted = "①旧\n0分00秒 → A\n周期：7分40秒";
    const notice = "⚠ 旧形式から移したタイムラインです。集結タイムライン計算で計算し直して読み込んでください";
    const dom = openWave({ storage: { waveTimerPastedTimeline: pasted } });
    t.after(() => dom.window.close());
    assert.equal($(dom, "#sourceStatus").textContent, notice);
    assert.equal($(dom, "#sourceStatus").classList.contains("warning"), true);
    assert.equal(JSON.parse(dom.window.localStorage.getItem("waveTimerTabs")).tabs[0].legacyTimeline, true);

    // 開き直しても注意を続け、追加したタブには出さない。
    const reopened = openWave({ storage: storageOf(dom) });
    t.after(() => reopened.window.close());
    assert.equal($(reopened, "#sourceStatus").textContent, notice);
    $(reopened, "#addTabBtn").click();
    assert.equal($(reopened, "#sourceStatus").textContent, "");
    clickTab(reopened, 0);
    assert.equal($(reopened, "#sourceStatus").textContent, notice);

    // 手で編集すると注意を消す（WAVE-075と同じ扱い）。
    setValue(reopened, $(reopened, "#pasteBox"), pasted + "\n");
    assert.equal($(reopened, "#sourceStatus").textContent, "");
    assert.equal(JSON.parse(reopened.window.localStorage.getItem("waveTimerTabs")).tabs[0].legacyTimeline, false);
  });

  test("旧形式から移したタイムラインは、計算元を読み込むと注意を消す（WAVE-077）", t => {
    const { storage } = siegeStorage(t);
    const dom = openWave({ storage: { ...storage, waveTimerPastedTimeline: "①旧\n0分00秒 → A\n周期：7分40秒" } });
    t.after(() => dom.window.close());
    assert.match($(dom, "#sourceStatus").textContent, /旧形式から移したタイムライン/);
    $(dom, "#loadSourceBtn").click();
    assert.equal($(dom, "#sourceStatus").textContent, "計算元：計算1から読み込み済み");
    assert.equal(JSON.parse(dom.window.localStorage.getItem("waveTimerTabs")).tabs[0].legacyTimeline, false);
  });

  test("旧形式の貼り付けが空か空白だけなら注意を出さない（WAVE-077）", t => {
    const settings = JSON.stringify({ periodMin: "1", periodSec: "5", maxMin: "2", maxSec: "0", extraDisplaySec: "7" });
    for (const pasted of ["", "  \n"]) {
      const dom = openWave({ storage: { waveTimerSettings: settings, waveTimerPastedTimeline: pasted } });
      t.after(() => dom.window.close());
      assert.equal($(dom, "#sourceStatus").textContent, "", JSON.stringify(pasted));
      assert.equal(JSON.parse(dom.window.localStorage.getItem("waveTimerTabs")).tabs[0].legacyTimeline, false);
    }
  });

  test("新しいキーが空か壊れていれば、旧キーから移し直す（WAVE-052）", t => {
    const settings = JSON.stringify({ periodMin: "1", periodSec: "5", maxMin: "2", maxSec: "0", extraDisplaySec: "7" });
    const pasted = "①旧\n0分00秒 → A\n周期：3分00秒";
    for (const broken of ["{壊れたJSON", '{"version":1,"tabs":[]}', ""]) {
      const dom = openWave({ storage: { waveTimerSettings: settings, waveTimerPastedTimeline: pasted, waveTimerTabs: broken } });
      t.after(() => dom.window.close());
      assert.equal($(dom, "#periodSec").value, "5", broken);
      assert.equal($(dom, "#pasteBox").value, pasted, broken);
      assert.equal(dom.window.localStorage.getItem("waveTimerSettings"), settings, broken);
      assert.equal(JSON.parse(dom.window.localStorage.getItem("waveTimerTabs")).tabs.length, 1, broken);
    }
  });

  test("新しいキーが空か壊れていて旧キーもなければ、既定値のタブを作る（WAVE-052）", t => {
    for (const broken of ["{壊れたJSON", '{"version":1,"tabs":[]}', ""]) {
      const dom = openWave({ storage: { waveTimerTabs: broken } });
      t.after(() => dom.window.close());
      assert.deepEqual(
        ["periodMin", "periodSec", "maxMin", "maxSec", "extraDisplaySec"].map(id => $(dom, "#" + id).value),
        ["0", "10", "0", "30", "3"], broken);
      assert.equal($(dom, "#pasteBox").value, "", broken);
      // 静的HTMLの既定値と区別するため、Scriptがタブを作って保存したことも確かめる。
      assert.deepEqual(tabs(dom).map(tab => tab.textContent), ["タイマー1"], broken);
      assert.equal(JSON.parse(dom.window.localStorage.getItem("waveTimerTabs")).tabs.length, 1, broken);
    }
  });

  test("旧キーがなければ既定値のタブを作る", t => {
    const dom = openWave();
    t.after(() => dom.window.close());
    assert.deepEqual(
      ["periodMin", "periodSec", "maxMin", "maxSec", "extraDisplaySec"].map(id => $(dom, "#" + id).value),
      ["0", "10", "0", "30", "3"]);
    assert.equal($(dom, "#pasteBox").value, "");
    assert.deepEqual(tabs(dom).map(tab => tab.textContent), ["タイマー1"]);
  });
});
