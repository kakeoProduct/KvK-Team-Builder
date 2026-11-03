"use strict";
// 決定的な乱数で作った入力を、集結タイムライン計算の実物で計算し、性質C1〜C3、C8〜C12と
// 出力の書式（SIEGE-020〜SIEGE-025）、周期ウェーブタイマーへ渡す結果（SIEGE-045）を検査する。
// 1件ごとに画面を操作するため時間がかかる。`node --test`はファイルを並列に実行するため、
// 入力をSHARDS個のファイル（siege-random-{番号}.test.js）へ分けて実行時間を縮める。

const test = require("node:test");
const assert = require("node:assert/strict");
const {
  DEFAULT_PET_BONUS, openSiege, fillSiege, calculate, readJson, createRandom, randomSiegeCase,
} = require("./helpers");
const { checkProperties } = require("./siege-properties");

const CASES = 1000;
const SHARDS = 4;
const SEED = 20261103;
// ページを開き直す間隔。ページ内の状態が増え続けないようにする。
const CASES_PER_PAGE = 50;
// 開き直すたびに、既定値と、保存した速度ペットのボーナス（SIEGE-046）を交互に使う。
// 小数のボーナスで、四捨五入（SIEGE-019）の境目に近い値も作る。
const CUSTOM_PET_BONUS = [0, 12.5, 0, 33.3, 50, 7.5, 100, 2, 41.7];

// 全件を同じ順で作り、shard番目（1始まり）が受け持つ入力だけを返す。
function shardCases(shard) {
  const rnd = createRandom(SEED);
  const cases = [];
  for (let i = 0; i < CASES; i++) {
    const testCase = randomSiegeCase(rnd);
    if (i % SHARDS === shard - 1) cases.push({ index: i, testCase });
  }
  return cases;
}

function bonusTableFor(page) {
  return page % 2 === 0 ? DEFAULT_PET_BONUS : CUSTOM_PET_BONUS;
}

function openPageFor(page) {
  const table = bonusTableFor(page);
  const storage = table === DEFAULT_PET_BONUS ? {} : { ksMarchPetBonus: JSON.stringify(table) };
  return openSiege({ storage });
}

function runShard(shard) {
  test(`決定的な乱数の入力${CASES}件のうち${shard}/${SHARDS}で、性質C1〜C3、C8〜C12と書式に違反しない`, t => {
    const cases = shardCases(shard);
    assert.ok(cases.length > 0, `shard ${shard}の入力が0件`);
    const failures = [];
    let dom = null;
    let page = -1;
    t.after(() => dom && dom.window.close());
    cases.forEach(({ index, testCase }, n) => {
      if (n % CASES_PER_PAGE === 0) {
        if (dom) dom.window.close();
        page += 1;
        dom = openPageFor(page);
      }
      fillSiege(dom, testCase);
      const { output, reference } = calculate(dom);
      let violations;
      try {
        violations = checkProperties(testCase, output, reference, {
          bonusTable: bonusTableFor(page),
          saved: readJson(dom, "siegeTimelineForWaveTimer"),
        });
      } catch (error) {
        violations = [`解析: ${error.stack}`];
      }
      if (violations.length) failures.push({ index, testCase, violations, output });
    });
    assert.deepEqual(failures.slice(0, 3), [], `違反した入力は${failures.length}件`);
  });
}

module.exports = { CASES, SHARDS, SEED, CUSTOM_PET_BONUS, shardCases, runShard };
