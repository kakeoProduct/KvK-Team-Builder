"use strict";
// 決定的な乱数で作った1000件の入力を、集結タイムライン計算の実物で計算し、性質C1〜C10を検査する。
// 1件ごとに画面を操作するため約30msかかる。`node --test`はファイルを並列に実行するため、
// 1000件をSHARDS個のファイル（siege-random-{番号}.test.js）へ分けて実行時間を縮める。

const test = require("node:test");
const assert = require("node:assert/strict");
const { openSiege, fillSiege, calculate, createRandom, randomSiegeCase } = require("./helpers");
const { checkProperties } = require("./siege-properties");

const CASES = 1000;
const SHARDS = 4;
const SEED = 12345;

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

function runShard(shard) {
  test(`決定的な乱数の入力${CASES}件のうち${shard}/${SHARDS}で、性質C1〜C10に違反しない`, t => {
    const cases = shardCases(shard);
    assert.ok(cases.length > 0, `shard ${shard}の入力が0件`);
    const failures = [];
    let dom = null;
    t.after(() => dom && dom.window.close());
    cases.forEach(({ index, testCase }, n) => {
      // 1つのページを使い回すと速いが、ページ内の状態が増え続けないよう50件ごとに開き直す。
      if (n % 50 === 0) {
        if (dom) dom.window.close();
        dom = openSiege();
      }
      fillSiege(dom, testCase);
      const { output, reference } = calculate(dom);
      let violations;
      try {
        violations = checkProperties(testCase, output, reference);
      } catch (error) {
        violations = [`解析: ${error.message}`];
      }
      if (violations.length) failures.push({ index, testCase, violations });
    });
    assert.deepEqual(failures.slice(0, 3), [], `違反した入力は${failures.length}件`);
  });
}

module.exports = { CASES, SHARDS, SEED, shardCases, runShard };
