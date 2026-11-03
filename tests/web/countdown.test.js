"use strict";
// KvK同着スタート カウントダウン表（web/KvK同着スタート カウントダウン表.html）を実物のまま動かす検査。
// 集結タイムライン計算と共有する速度ペットのボーナス（SIEGE-046、CDOWN-004）だけを確かめる（COM-054）。
// 要件IDはdocs/requirements/web-tools/sync-start-countdown.mdとsiege-timeline.mdを参照する。

const test = require("node:test");
const assert = require("node:assert/strict");
const { openCountdown, openSiege, setValue, $, $$ } = require("./helpers");

const BONUS_KEY = "ksMarchPetBonus";

function open(t, opener, options) {
  const dom = opener(options);
  t.after(() => dom.window.close());
  return dom;
}

const optionTexts = select => Array.from(select.options).map(o => o.textContent);

test.describe("速度ペットのボーナスの共有（SIEGE-046、CDOWN-004）", () => {
  test("ボーナスを変えると、結果を表示していれば計算し直す（CDOWN-004、CDOWN-011）", t => {
    const dom = open(t, openCountdown);
    // サンプルの1行目（到着秒数36）にLv8を選ぶ。既定の30%では36 ÷ 1.3 = 27.69…を四捨五入して28秒。
    // 最長は43秒のため、最後の出発カウントは43 - 28 = 15になる（1列目の先頭の値）。
    setValue(dom, $(dom, ".f-pet"), "8", "change");
    $(dom, "button[onclick='compute()']").click();
    const firstCount = () => $(dom, "#result-table tbody tr td").textContent;
    assert.equal(firstCount(), "15");
    // 80.5%にすると36 ÷ 1.805 = 19.94…で20秒、最後の出発カウントは43 - 20 = 23になる。
    setValue(dom, $(dom, '.pb-edit input[data-lv="8"]'), "80.5", "change");
    assert.equal(firstCount(), "23");
  });

  test("集結タイムライン計算で保存したボーナスを、カウントダウン表の選択肢と行軍秒数に使う", t => {
    const bonus = [0, 15, 17, 19, 21, 23, 25, 27, 80.5];
    const dom = open(t, openCountdown, { storage: { [BONUS_KEY]: JSON.stringify(bonus) } });
    const select = $(dom, ".f-pet");
    assert.deepEqual(optionTexts(select).slice(0, 2), ["持っていない", "Lv8（+80.5%）"]);
    // サンプルの1行目は到着秒数36。Lv8を選ぶと36 ÷ 1.805 = 19.94…を四捨五入した20を表示する（CDOWN-001）。
    setValue(dom, select, "8", "change");
    assert.equal($(dom, ".f-march-pet").value, "20");
  });

  test("カウントダウン表で編集したボーナスを同じキーへ保存し、集結タイムライン計算が読む", t => {
    const countdown = open(t, openCountdown);
    setValue(countdown, $(countdown, '.pb-edit input[data-lv="1"]'), "50", "change");
    const saved = countdown.window.localStorage.getItem(BONUS_KEY);
    assert.deepEqual(JSON.parse(saved), [0, 50, 17, 19, 21, 23, 25, 27, 30]);
    // 名簿の選択肢も、変えた値で作り直す（CDOWN-004）。
    assert.ok(optionTexts($(countdown, ".f-pet")).includes("Lv1（+50%）"));

    const siege = open(t, openSiege, { storage: { [BONUS_KEY]: saved } });
    assert.ok(optionTexts($(siege, ".pet-select")).includes("Lv1（+50%）"));
    assert.equal($$(siege, '.pb-edit input[data-lv="1"]')[0].value, "50");
  });
});
