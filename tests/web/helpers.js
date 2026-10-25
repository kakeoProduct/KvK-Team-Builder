"use strict";
// 実物のweb/のHTMLをjsdomで読み込み、画面と同じ操作で動かすための補助（ADR 0030）。

const fs = require("node:fs");
const path = require("node:path");
const { JSDOM } = require("jsdom");

const WEB_DIR = path.resolve(__dirname, "..", "..", "web");
const SIEGE_HTML = path.join(WEB_DIR, "攻城タイムライン計算.html");
const WAVE_HTML = path.join(WEB_DIR, "周期ウェーブタイマー.html");
const ORIGIN = "https://example.test/web/";

const htmlCache = new Map();
function readHtml(file) {
  if (!htmlCache.has(file)) htmlCache.set(file, fs.readFileSync(file, "utf8"));
  return htmlCache.get(file);
}

// performance.nowとrequestAnimationFrameを差し替え、時刻を手で進める時計。
function createClock(start = 1000) {
  let now = start;
  let frames = new Map();
  let nextId = 1;
  return {
    install(window) {
      Object.defineProperty(window.performance, "now", { configurable: true, value: () => now });
      window.requestAnimationFrame = callback => {
        const id = nextId++;
        frames.set(id, callback);
        return id;
      };
      window.cancelAnimationFrame = id => { frames.delete(id); };
    },
    now: () => now,
    // 時刻を進め、その時点で待っている描画を1回実行する。
    advance(ms) {
      now += ms;
      const pending = frames;
      frames = new Map();
      pending.forEach(callback => callback(now));
    },
  };
}

// storageは開く前のlocalStorageの内容、confirmは削除の確認への応答を返す関数。
function openPage(file, { storage = {}, clock = null, confirm = () => true } = {}) {
  const dom = new JSDOM(readHtml(file), {
    runScripts: "dangerously",
    url: ORIGIN + encodeURIComponent(path.basename(file)),
    pretendToBeVisual: true,
    beforeParse(window) {
      Object.entries(storage).forEach(([key, value]) => window.localStorage.setItem(key, value));
      window.confirm = message => confirm(message);
      window.navigator.clipboard = { writeText: () => Promise.resolve() };
      if (clock) clock.install(window);
    },
  });
  return dom;
}

function openSiege(options) {
  return openPage(SIEGE_HTML, options);
}

function openWave(options) {
  return openPage(WAVE_HTML, options);
}

function storageOf(dom) {
  const result = {};
  const storage = dom.window.localStorage;
  for (let i = 0; i < storage.length; i++) {
    const key = storage.key(i);
    result[key] = storage.getItem(key);
  }
  return result;
}

function setValue(dom, element, value, type = "input") {
  element.value = String(value);
  element.dispatchEvent(new dom.window.Event(type, { bubbles: true }));
}

// 値が変わるときだけ入力の通知を送る。画面の描き直しを減らして検査を速くする。
function changeValue(dom, element, value, type = "input") {
  if (element.value !== String(value)) setValue(dom, element, value, type);
}

function $(dom, selector) {
  return dom.window.document.querySelector(selector);
}

function $$(dom, selector) {
  return Array.from(dom.window.document.querySelectorAll(selector));
}

function tabs(dom) {
  return $$(dom, "#tabList [role=tab]");
}

function selectedTab(dom) {
  return $(dom, '#tabList [role=tab][aria-selected="true"]');
}

function clickTab(dom, index) {
  tabs(dom)[index].click();
}

// --- 集結タイムライン計算の入力を、画面の操作だけで入れ替える ---
// testCaseは {settings: {kz, mr, gap, buf}, members: [[役割, ラベル, 行軍秒数]], patterns: [[削りのラベル]]}
// 1000件を1つのページで続けて動かすため、既存の行は使い回し、増減した分だけ追加と削除をする。
function fillSiege(dom, testCase) {
  const { settings, members, patterns } = testCase;
  while ($$(dom, ".pattern-block").length > patterns.length) {
    $$(dom, ".del-pattern-btn").pop().click();
  }
  // 削りから役割を変えた行はパターンの選択に残る（KI-SIEGE-01）ため、役割を変える前に選択を外す。
  $$(dom, ".pattern-block input[type=checkbox]:checked").forEach(box => box.click());
  while ($$(dom, "#memberBody tr").length > members.length) {
    $$(dom, ".del-member-btn").pop().click();
  }
  while ($$(dom, "#memberBody tr").length < members.length) $(dom, "#addMemberBtn").click();

  const ids = $$(dom, "#memberBody .role-select").map(select => select.dataset.id);
  const idByLabel = {};
  members.forEach(([role, label, march], i) => {
    const id = ids[i];
    // 役割とラベルの変更でパターンの欄が描き直されるため、欄はidで取り直す。
    changeValue(dom, $(dom, `.role-select[data-id="${id}"]`), role, "change");
    changeValue(dom, $(dom, `.label-input[data-id="${id}"]`), label);
    changeValue(dom, $(dom, `.march-input[data-id="${id}"]`), march);
    idByLabel[label] = id;
  });

  while ($$(dom, ".pattern-block").length < patterns.length) $(dom, "#addPatternBtn").click();
  const pids = $$(dom, ".pattern-name-input").map(input => input.dataset.pid);
  patterns.forEach((labels, i) => {
    const wanted = new Set(labels.map(label => idByLabel[label]));
    $$(dom, `input[type=checkbox][data-pid="${pids[i]}"]`).forEach(box => {
      if (box.checked !== wanted.has(box.dataset.mid)) box.click();
    });
  });

  changeValue(dom, $(dom, "#kezuriRallyMin"), settings.kz);
  changeValue(dom, $(dom, "#mainRallyMin"), settings.mr);
  changeValue(dom, $(dom, "#phaseGap"), settings.gap);
  changeValue(dom, $(dom, "#buffer"), settings.buf);
}

function calculate(dom) {
  $(dom, "#calcBtn").click();
  return {
    output: $(dom, "#output").textContent,
    reference: $(dom, "#refOutput").textContent,
  };
}

// --- 決定的な乱数（mulberry32） ---
function createRandom(seed) {
  let state = seed;
  const next = () => {
    state |= 0;
    state = (state + 0x6d2b79f5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  return (lo, hi) => lo + Math.floor(next() * (hi - lo + 1));
}

// docs/requirements/web-tools/siege-timeline.mdの「計算結果が満たす性質」に書いた範囲で入力を作る。
function randomSiegeCase(rnd) {
  const settings = { kz: rnd(1, 5), mr: rnd(1, 5), gap: rnd(0, 3), buf: rnd(0, 60) };
  const members = [];
  const mains = rnd(1, 2);
  const reinforcements = rnd(0, 2);
  const kezuri = rnd(1, 8);
  for (let i = 0; i < mains; i++) members.push(["メイン", "M" + i, rnd(0, 150)]);
  for (let i = 0; i < reinforcements; i++) members.push(["増援", "R" + i, rnd(0, 150)]);
  for (let i = 0; i < kezuri; i++) members.push(["削り", "K" + i, rnd(0, 150)]);
  const patterns = [];
  const count = rnd(1, 5);
  for (let p = 0; p < count; p++) {
    const chosen = members.filter(m => m[0] === "削り" && rnd(0, 2) === 0).map(m => m[1]);
    patterns.push(chosen.length ? chosen : ["K" + rnd(0, kezuri - 1)]);
  }
  return { settings, members, patterns };
}

module.exports = {
  SIEGE_HTML,
  WAVE_HTML,
  createClock,
  openSiege,
  openWave,
  storageOf,
  setValue,
  $,
  $$,
  tabs,
  selectedTab,
  clickTab,
  fillSiege,
  calculate,
  createRandom,
  randomSiegeCase,
};
