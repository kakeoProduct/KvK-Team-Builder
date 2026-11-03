"use strict";
// 実物のweb/のHTMLをjsdomで読み込み、画面と同じ操作で動かすための補助（ADR 0030、ADR 0031）。

const fs = require("node:fs");
const path = require("node:path");
const { JSDOM } = require("jsdom");

const WEB_DIR = path.resolve(__dirname, "..", "..", "web");
const SIEGE_HTML = path.join(WEB_DIR, "攻城タイムライン計算.html");
const WAVE_HTML = path.join(WEB_DIR, "周期ウェーブタイマー.html");
const COUNTDOWN_HTML = path.join(WEB_DIR, "KvK同着スタート カウントダウン表.html");
const PET_BONUS_JS = path.join(WEB_DIR, "pet-bonus.js");
const PET_BONUS_TAG = '<script src="pet-bonus.js"></script>';
const ORIGIN = "https://example.test/web/";

// web/pet-bonus.jsの既定値（SIEGE-019、SIEGE-046）。先頭はペットなし、続いてLv1〜Lv8。
const DEFAULT_PET_BONUS = [0, 15, 17, 19, 21, 23, 25, 27, 30];

// jsdomは外部のscriptを読み込まないため、共通部品のscriptタグを同じ中身のインラインscriptへ置き換える。
// タグが見つからなければ、読み込み方が変わったことに気づけるよう失敗させる。
const htmlCache = new Map();
function readHtml(file) {
  if (!htmlCache.has(file)) {
    let html = fs.readFileSync(file, "utf8");
    if (html.includes(PET_BONUS_TAG)) {
      const script = fs.readFileSync(PET_BONUS_JS, "utf8");
      html = html.replace(PET_BONUS_TAG, () => `<script>\n${script}\n</script>`);
    } else if (file === SIEGE_HTML || file === COUNTDOWN_HTML) {
      throw new Error(`${path.basename(file)}に${PET_BONUS_TAG}が見つかりません`);
    }
    htmlCache.set(file, html);
  }
  return htmlCache.get(file);
}

// performance.now、setTimeout、requestAnimationFrameを差し替え、時刻を手で進める時計。
// Date.nowは差し替えない（保存時刻savedAtは、操作の前後で読んだ実時刻の範囲で確かめる）。
function createClock(start = 1000) {
  let now = start;
  let frames = new Map();
  const timers = new Map();
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
      window.setTimeout = (callback, delay = 0) => {
        const id = nextId++;
        timers.set(id, { callback, due: now + Math.max(0, Number(delay) || 0), id });
        return id;
      };
      window.clearTimeout = id => { timers.delete(id); };
    },
    now: () => now,
    // 時刻を進めてから、期限の来たタイマーを期限の順にすべて実行し、待っている描画を1回実行する。
    // 時刻を先に進めるため、タイマーはブラウザのタブが休止していたときのように遅れて実行される。
    advance(ms) {
      now += ms;
      for (;;) {
        const due = Array.from(timers.values())
          .filter(timer => timer.due <= now)
          .sort((a, b) => a.due - b.due || a.id - b.id);
        if (!due.length) break;
        timers.delete(due[0].id);
        due[0].callback();
      }
      const pending = frames;
      frames = new Map();
      pending.forEach(callback => callback(now));
    },
    // 小刻みに進める。期限どおりにタイマーが実行される場合を再現する。
    advanceBy(ms, step = 100) {
      for (let done = 0; done < ms; done += step) this.advance(Math.min(step, ms - done));
    },
  };
}

// storageは開く前のlocalStorageの内容、confirmは確認への応答を返す関数、
// beforeParseはscriptを実行する前にwindowへ加える処理。
function openPage(file, { storage = {}, clock = null, confirm = () => true, clipboard = null, beforeParse = null } = {}) {
  const dom = new JSDOM(readHtml(file), {
    runScripts: "dangerously",
    url: ORIGIN + encodeURIComponent(path.basename(file)),
    pretendToBeVisual: true,
    beforeParse(window) {
      Object.entries(storage).forEach(([key, value]) => window.localStorage.setItem(key, value));
      window.confirm = message => confirm(message);
      window.navigator.clipboard = clipboard || { writeText: () => Promise.resolve() };
      if (clock) clock.install(window);
      if (beforeParse) beforeParse(window);
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

function openCountdown(options) {
  return openPage(COUNTDOWN_HTML, options);
}

// localStorageを使えない環境（COM-041）。openPageのbeforeParseへ渡す。
const STORAGE_FAILURES = {
  // 書き込みが例外を投げる（容量不足など）。
  setItemThrows(window) {
    window.Storage.prototype.setItem = () => { throw new window.DOMException("quota", "QuotaExceededError"); };
  },
  // localStorageの取得そのものが例外を投げる（サイトのデータを拒否した設定など）。
  getterThrows(window) {
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      get() { throw new window.DOMException("denied", "SecurityError"); },
    });
  },
};

function storageOf(dom) {
  const result = {};
  const storage = dom.window.localStorage;
  for (let i = 0; i < storage.length; i++) {
    const key = storage.key(i);
    result[key] = storage.getItem(key);
  }
  return result;
}

function readJson(dom, key) {
  const raw = dom.window.localStorage.getItem(key);
  return raw === null ? null : JSON.parse(raw);
}

function setValue(dom, element, value, type = "input") {
  element.value = String(value);
  element.dispatchEvent(new dom.window.Event(type, { bubbles: true }));
}

// 値が変わるときだけ入力の通知を送る。画面の描き直しを減らして検査を速くする。
function changeValue(dom, element, value, type = "input") {
  if (element.value !== String(value)) setValue(dom, element, value, type);
}

// チェックボックスを画面と同じくクリックで切り替える。
function setChecked(element, checked) {
  if (element.checked !== checked) element.click();
}

function $(dom, selector) {
  return dom.window.document.querySelector(selector);
}

function $$(dom, selector) {
  return Array.from(dom.window.document.querySelectorAll(selector));
}

// --- 集結タイムライン計算の入力を、画面の操作だけで入れ替える ---
// testCaseは次の形とする。petSameは「全員同じ」を使わないならnull、使うなら共通の採用値。
// {settings: {kz, mr, gap, buf}, petSame,
//  members: [{role, label, march, pet, usePet}],
//  patterns: [{kezuri: [ラベル], reinforce: [ラベル]}]}
// 多数の入力を1つのページで続けて動かすため、既存の行は使い回し、増減した分だけ追加と削除をする。
function fillSiege(dom, testCase) {
  const { settings, members, patterns, petSame = null } = testCase;
  while ($$(dom, ".pattern-block").length > patterns.length) {
    $$(dom, ".del-pattern-btn").pop().click();
  }
  // 削りや増援から役割を変えた行はパターンの選択に残る（KI-SIEGE-01）。その状態を作らないよう、
  // 役割を変える前にすべての選択を外す。
  $$(dom, ".pattern-block input[type=checkbox]:checked").forEach(box => box.click());
  // 行ごとの採用は「全員同じ」がオフでないと変えられない（SIEGE-008）。
  setChecked($(dom, "#petSameAllCheckbox"), false);
  while ($$(dom, "#memberBody tr").length > members.length) {
    $$(dom, ".del-member-btn").pop().click();
  }
  while ($$(dom, "#memberBody tr").length < members.length) $(dom, "#addMemberBtn").click();

  const ids = $$(dom, "#memberBody .role-select").map(select => select.dataset.id);
  const idByLabel = {};
  members.forEach((member, i) => {
    const id = ids[i];
    // 役割とラベルの変更でパターンの欄が描き直されるため、欄はidで取り直す。
    changeValue(dom, $(dom, `.role-select[data-id="${id}"]`), member.role, "change");
    changeValue(dom, $(dom, `.label-input[data-id="${id}"]`), member.label);
    changeValue(dom, $(dom, `.march-input[data-id="${id}"]`), member.march);
    changeValue(dom, $(dom, `.pet-select[data-id="${id}"]`), member.pet || 0, "change");
    setChecked($(dom, `.use-pet-checkbox[data-id="${id}"]`), member.usePet !== false);
    idByLabel[member.label] = id;
  });
  if (petSame !== null) {
    setChecked($(dom, "#petSameAllCheckbox"), true);
    setChecked($(dom, "#petSameValueCheckbox"), petSame);
  }

  while ($$(dom, ".pattern-block").length < patterns.length) $(dom, "#addPatternBtn").click();
  const pids = $$(dom, ".pattern-name-input").map(input => input.dataset.pid);
  patterns.forEach((pattern, i) => {
    // 削除と追加を繰り返すと名前が重複する（KI-SIEGE-08）ため、名前は定義順の記号に入れ直す。
    changeValue(dom, $(dom, `.pattern-name-input[data-pid="${pids[i]}"]`), circledNumber(i + 1));
    const wanted = {
      kezuri: pattern.kezuri.map(label => idByLabel[label]),
      reinforce: pattern.reinforce.map(label => idByLabel[label]),
    };
    // いったんすべて外してから、パターンに書いた順にクリックする。追加したパターンは増援を全員選んだ状態で
    // 作られる（SIEGE-003）ため、外さないと増援がメンバー表の順で残る。実装は選んだ順を保存するため、
    // 画面の並び（メンバー表の順）と違う順で選んでも、出力がメンバー表の順になることを確かめられる（SIEGE-024）。
    $$(dom, `input[type=checkbox][data-pid="${pids[i]}"]`).forEach(box => setChecked(box, false));
    for (const type of ["kezuri", "reinforce"]) {
      wanted[type].forEach(mid => {
        setChecked($(dom, `input[type=checkbox][data-pid="${pids[i]}"][data-type="${type}"][data-mid="${mid}"]`), true);
      });
    }
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

// SIEGE-003のパターン名。①〜⑳、21個目以降は(21)の形式。
function circledNumber(n) {
  const circled = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳";
  return n <= circled.length ? circled[n - 1] : `(${n})`;
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
// 既知の不具合に当たる入力は作らない。選ぶ削りと増援の順は、メンバー表の順と違う順にも入れ替える。
// - メインは1人以上とする。性質を確かめる入力の範囲（siege-timeline.mdの「計算結果が満たす性質」）に合わせる。
//   メインが0人の計算（SIEGE-018）はsiege-timeline.test.jsの固定の例で確かめる
// - 集結時間は1分以上の整数、行軍秒数とフェーズ間隔とバッファは0以上の整数とする。小数と負数は
//   KI-SIEGE-06、KI-SIEGE-07に当たる
// - ラベルは空にせず、重複させない。空のラベルは出力で空文字になり（KI-SIEGE-09）、出力から人を区別できない
function randomSiegeCase(rnd) {
  const settings = { kz: rnd(1, 5), mr: rnd(1, 5), gap: rnd(0, 3), buf: rnd(0, 60) };
  const members = [];
  const add = (role, label) => {
    const pet = rnd(0, 2) === 0 ? 0 : rnd(1, 8);
    members.push({ role, label, march: rnd(0, 150), pet, usePet: rnd(0, 2) !== 0 });
  };
  const mains = rnd(1, 2);
  const reinforcements = rnd(0, 2);
  const kezuri = rnd(1, 8);
  for (let i = 0; i < mains; i++) add("メイン", "M" + i);
  for (let i = 0; i < reinforcements; i++) add("増援", "R" + i);
  for (let i = 0; i < kezuri; i++) add("削り", "K" + i);
  // 行の並びが入力の並びに頼らないよう、メンバーの並びを入れ替える。
  for (let i = members.length - 1; i > 0; i--) {
    const j = rnd(0, i);
    [members[i], members[j]] = [members[j], members[i]];
  }
  const shuffle = list => {
    const result = [...list];
    for (let i = result.length - 1; i > 0; i--) {
      const j = rnd(0, i);
      [result[i], result[j]] = [result[j], result[i]];
    }
    return result;
  };
  const petSame = rnd(0, 3) === 0 ? rnd(0, 1) === 1 : null;
  const patterns = [];
  const count = rnd(1, 5);
  const labelsOf = role => members.filter(m => m.role === role).map(m => m.label);
  for (let p = 0; p < count; p++) {
    // 削りを選ばないパターンも作る（SIEGE-018）。
    const chosen = rnd(0, 5) === 0 ? [] : labelsOf("削り").filter(() => rnd(0, 2) === 0);
    patterns.push({
      kezuri: shuffle(chosen.length || rnd(0, 5) === 0 ? chosen : [labelsOf("削り")[rnd(0, kezuri - 1)]]),
      reinforce: shuffle(labelsOf("増援").filter(() => rnd(0, 1) === 0)),
    });
  }
  return { settings, petSame, members, patterns };
}

module.exports = {
  SIEGE_HTML,
  WAVE_HTML,
  COUNTDOWN_HTML,
  STORAGE_FAILURES,
  DEFAULT_PET_BONUS,
  createClock,
  openSiege,
  openWave,
  openCountdown,
  storageOf,
  readJson,
  setValue,
  changeValue,
  setChecked,
  $,
  $$,
  fillSiege,
  calculate,
  circledNumber,
  createRandom,
  randomSiegeCase,
};
