"use strict";
// 集結タイムライン計算の出力テキストと入力だけから、計算結果が満たす性質C1〜C3、C8〜C12と、
// 出力の書式（SIEGE-020〜SIEGE-025）、周期ウェーブタイマーへ渡す結果（SIEGE-045）を判定する。
// 性質の定義はdocs/requirements/web-tools/siege-timeline.mdの「計算結果が満たす性質」にある。
// 計算の実装を読まず、出力された時刻と、入力と要件の式だけを使う。
// C4はブロックの並び（SIEGE-025）が周ごとに変わり得るため、C5〜C7は現行の周期の計算で満たさないことが
// ある（KI-SIEGE-14）ため、判定しない（ADR 0031）。C9のうち並びの違反は、書式の要件の名前（SIEGE-024）で報告する。

const { DEFAULT_PET_BONUS, circledNumber } = require("./helpers");

const toSeconds = text => {
  const matched = text.match(/^(\d+)分(\d{2})秒$/);
  if (!matched) throw new Error("時刻ではありません: " + text);
  return Number(matched[1]) * 60 + Number(matched[2]);
};

const TIME = "\\d+分\\d{2}秒";
const LINE_RE = new RegExp(
  `^(${TIME}) → (.+?)（(\\d+)分(?:(\\d+)秒)?集結）※行軍(-?[\\d.]+)秒（(${TIME})着、(${TIME})帰還）$`);
const HEADER_RE = /^(.*?)(→メイン→増援|→メイン)$/;

// パターン名で始まる文字列を、定義順のパターン名で分ける。
function splitName(text, names) {
  const name = names.find(n => text.startsWith(n));
  if (name === undefined) throw new Error("パターン名で始まりません: " + text);
  return { name, rest: text.slice(name.length) };
}

// 1周分の行を [{name, header, kezuriLabels, withReinforce, lines}] へ分解する。空行でブロックを区切る。
function parseRound(lines, names) {
  const blocks = [];
  let block = null;
  for (const line of lines) {
    let matched;
    if (!line) {
      block = null;
    } else if ((matched = line.match(LINE_RE))) {
      if (!block) throw new Error("見出しのない行: " + line);
      const { name, rest } = splitName(matched[2], names);
      if (name !== block.name) throw new Error(`見出し${block.header}のブロックに別のパターンの行: ${line}`);
      block.lines.push({
        text: line,
        launch: toSeconds(matched[1]),
        label: rest,
        rally: Number(matched[3]) * 60 + Number(matched[4] || 0),
        rallyText: line.match(/（(.+?)集結）/)[1],
        march: Number(matched[5]),
        arrival: toSeconds(matched[6]),
        ret: toSeconds(matched[7]),
      });
    } else if (!block && (matched = line.match(HEADER_RE))) {
      const { name, rest } = splitName(matched[1], names);
      block = {
        name,
        header: line,
        kezuriLabels: rest ? rest.split("+") : [],
        withReinforce: matched[2] === "→メイン→増援",
        lines: [],
      };
      blocks.push(block);
    } else {
      throw new Error("解析できない行: " + line);
    }
  }
  return blocks;
}

// 「計算結果（1周目）」を {blocks, cycle} へ分解する。末尾は空行と`周期：`の行（SIEGE-020）。
function parseOutput(text, names) {
  const lines = text.split("\n");
  const last = lines.pop();
  const matched = last.match(/^周期：(.+)$/);
  if (!matched) throw new Error("末尾が周期の行ではありません: " + last);
  if (lines.pop() !== "") throw new Error("周期の行の前が空行ではありません");
  return { blocks: parseRound(lines, names), cycle: toSeconds(matched[1]), cycleLine: last };
}

// 「参考：2周分の計算結果」を {rounds, cycle, firstText} へ分解する（SIEGE-021）。
function parseReference(text, names) {
  const matched = text.match(/^【1周目】\n([\s\S]*)\n\n【2周目】\n([\s\S]*)\n\n(周期：.+)$/);
  if (!matched) throw new Error("参考の結果の形式が違います");
  const cycle = toSeconds(matched[3].slice("周期：".length));
  return {
    rounds: [parseRound(matched[1].split("\n"), names), parseRound(matched[2].split("\n"), names)],
    cycle,
    cycleLine: matched[3],
    firstText: matched[1],
  };
}

// 要件の式で、メンバーの行軍を求める（SIEGE-019、C12）。
function expectedMarch(member, petSame, bonusTable = DEFAULT_PET_BONUS) {
  const usePet = petSame === null || petSame === undefined ? member.usePet !== false : petSame;
  if (!usePet) return member.march;
  const bonus = bonusTable[member.pet || 0] || 0;
  return Math.round(member.march / (1 + bonus / 100));
}

const ROLE_ORDER = { 削り: 0, メイン: 1, 増援: 2 };

// 違反した性質の名前と理由の一覧を返す。空なら全性質を満たす。
// savedは周期ウェーブタイマーへ渡す結果（SIEGE-045）。省略すると判定しない。
function checkProperties(testCase, output, reference, { bonusTable = DEFAULT_PET_BONUS, saved = null } = {}) {
  const { settings, members, patterns, petSame = null } = testCase;
  const violations = [];
  const fail = (name, detail) => violations.push(`${name}: ${detail}`);
  const names = patterns.map((_, i) => circledNumber(i + 1));

  if (/-\d|NaN|undefined/.test(reference) || /-\d|NaN|undefined/.test(output)) {
    fail("C1", "負の時刻、NaN、またはundefined");
    return violations;
  }
  let ref;
  let out;
  try {
    ref = parseReference(reference, names);
    out = parseOutput(output, names);
  } catch (error) {
    fail("形式", error.message);
    return violations;
  }

  const member = Object.fromEntries(members.map(m => [m.label, m]));
  const position = Object.fromEntries(members.map((m, i) => [m.label, i]));
  const march = label => expectedMarch(member[label], petSame, bonusTable);
  const rally = { 削り: settings.kz * 60, メイン: settings.mr * 60, 増援: settings.mr * 60 };
  const offset = { 削り: 0, メイン: settings.gap, 増援: 2 * settings.gap };
  const labelsOf = role => members.filter(m => m.role === role).map(m => m.label);
  const sorted = list => [...list].sort().join(",");
  // 行が1つもないパターンは出さない（SIEGE-024）。メインがいれば全パターンに行がある（SIEGE-018）。
  const active = names.filter((_, i) =>
    patterns[i].kezuri.length || labelsOf("メイン").length || patterns[i].reinforce.length);

  // C9: 入力どおりのパターン数で、各パターンの見出しと行の集合が入力と一致する（SIEGE-018、SIEGE-024）。
  // 入力の入れ替え漏れや行の欠落を、時刻の性質より先に検出する。
  ref.rounds.forEach((round, r) => {
    const shown = round.map(b => b.name);
    if (sorted(shown) !== sorted(active) || new Set(shown).size !== shown.length) {
      fail("C9", `${r + 1}周目のパターン${shown.join(",")}、期待${active.join(",")}`);
      return;
    }
    round.forEach(block => {
      const pattern = patterns[names.indexOf(block.name)];
      // 見出しの削りのラベルは、選んだ順や名前の順ではなくメンバー表の順に並ぶ（SIEGE-024）。
      const headerLabels = members.filter(m => pattern.kezuri.includes(m.label)).map(m => m.label);
      if (block.kezuriLabels.join("+") !== headerLabels.join("+")) {
        fail("SIEGE-024", `${r + 1}周目の見出し${block.header}の削り、期待${headerLabels.join("+")}`);
      }
      if (block.withReinforce !== pattern.reinforce.length > 0) {
        fail("C9", `${r + 1}周目の見出し${block.header}の末尾`);
      }
      const expected = [...pattern.kezuri, ...labelsOf("メイン"), ...pattern.reinforce];
      const actual = block.lines.map(l => l.label);
      if (sorted(actual) !== sorted(expected)) {
        fail("C9", `${r + 1}周目${block.header}の行${actual.join(",")}、期待${expected.join(",")}`);
      }
    });
  });
  if (violations.length) return violations;

  // 書式（SIEGE-023〜SIEGE-025）: 集結時間の表記、行とブロックの並び。
  ref.rounds.forEach((round, r) => {
    round.forEach(block => block.lines.forEach(l => {
      const role = member[l.label].role;
      const expectedRally = rally[role] % 60 ? `${Math.floor(rally[role] / 60)}分${rally[role] % 60}秒` : `${rally[role] / 60}分`;
      if (l.rallyText !== expectedRally) fail("SIEGE-023", `${l.text}の集結時間、期待${expectedRally}`);
    }));
    round.forEach(block => block.lines.forEach((l, k) => {
      if (k === 0) return;
      const prev = block.lines[k - 1];
      const order = ROLE_ORDER[member[prev.label].role] - ROLE_ORDER[member[l.label].role];
      // 同じ発起で同じ役割の行は、メンバー表の順に並ぶ（SIEGE-024）。
      const tableOrder = position[prev.label] - position[l.label];
      if (prev.launch > l.launch || (prev.launch === l.launch && (order > 0 || (order === 0 && tableOrder > 0)))) {
        fail("SIEGE-024", `${r + 1}周目${block.header}の行の並び: ${prev.text} / ${l.text}`);
      }
    }));
    round.forEach((block, k) => {
      if (k === 0) return;
      const prev = round[k - 1];
      const a = prev.lines[0].launch;
      const b = block.lines[0].launch;
      if (a > b || (a === b && names.indexOf(prev.name) > names.indexOf(block.name))) {
        fail("SIEGE-025", `${r + 1}周目のブロックの並び: ${prev.header} / ${block.header}`);
      }
    });
  });

  // C12: 行軍は、採用と速度ペットからSIEGE-019の式で求めた値に等しい。
  ref.rounds.flat().forEach(block => block.lines.forEach(l => {
    if (l.march !== march(l.label)) fail("C12", `${l.text}の行軍、期待${march(l.label)}`);
  }));

  // パターンごとのT。削りがいれば削りの着弾、いなければメインの着弾 - フェーズ間隔（SIEGE-014）。
  // 定義順のパターン名で引けるよう、周ごとに名前 -> ブロックの表を作る。
  const byName = ref.rounds.map(round => Object.fromEntries(round.map(b => [b.name, b])));
  const T = byName.map(round => active.map(name => {
    const lines = round[name].lines;
    const kezuri = lines.filter(l => member[l.label].role === "削り");
    if (kezuri.length) return kezuri[0].arrival;
    const main = lines.find(l => member[l.label].role === "メイン");
    if (main) return main.arrival - settings.gap;
    return lines[0].arrival - 2 * settings.gap;
  }));

  // C1: 発起が0秒より前にならない。
  ref.rounds.flat().forEach(block => block.lines.forEach(l => {
    if (l.launch < 0) fail("C1", `${l.text}`);
  }));

  // C3: 階段状の着弾。発起と帰還はSIEGE-015の式に従う。
  byName.forEach((round, r) => active.forEach((name, i) => round[name].lines.forEach(l => {
    const role = member[l.label].role;
    if (l.arrival !== T[r][i] + offset[role]) fail("C3", `${r + 1}周目${l.text}の着弾、T=${T[r][i]}`);
    if (l.launch !== l.arrival - rally[role] - march(l.label)) fail("C3", `${r + 1}周目${l.text}の発起`);
    if (l.ret !== l.arrival + march(l.label)) fail("C3", `${r + 1}周目${l.text}の帰還`);
  })));

  // C10: 1周目、2周目の順に定義順で確定したとき、各パターンのTは、それより前に確定したパターンの
  // 帰還 + パターン間バッファから求めた使用可能時刻で、SIEGE-012の最大値に等しい。
  // 着弾を必要以上に遅らせる退行は、C1〜C3をすべて満たしたままになるため、ここで検出する。
  // C2: あわせて、同じ人の次の発起が前回の帰還 + パターン間バッファ以降であることを確かめる。
  const ready = {};
  const lastUse = {};
  byName.forEach((round, r) => active.forEach((name, i) => {
    const candidates = [0];
    round[name].lines.forEach(l => {
      const role = member[l.label].role;
      candidates.push((ready[l.label] || 0) + rally[role] + march(l.label) - offset[role]);
    });
    const expected = Math.max(...candidates);
    if (T[r][i] !== expected) fail("C10", `${r + 1}周目${round[name].header}のT${T[r][i]}、期待${expected}`);
    round[name].lines.forEach(l => {
      const prev = lastUse[l.label];
      if (prev && l.launch < prev.ret + settings.buf) {
        fail("C2", `${l.label}: 発起${l.launch} < 帰還${prev.ret}+${settings.buf}`);
      }
      lastUse[l.label] = l;
      ready[l.label] = l.ret + settings.buf;
    });
  }));

  // C11: 表示した周期は、先頭のパターンの2周目と1周目の着弾の差に等しい（SIEGE-017）。
  // 先頭のパターンに行がなければ、出力から着弾を読めないため判定しない。
  if (active[0] === names[0] && ref.cycle !== T[1][0] - T[0][0]) {
    fail("C11", `周期${ref.cycle}、期待${T[1][0] - T[0][0]}`);
  }

  // C8: 「計算結果（1周目）」は、参考の1周目と同じ本文に`周期：`の行を付けたもの（SIEGE-020、SIEGE-021）。
  if (output !== `${ref.firstText}\n\n${ref.cycleLine}`) fail("C8", "1周目の出力が参考の1周目と一致しない");
  if (out.cycle !== ref.cycle) fail("C8", "1周目の出力と参考の周期が違う");

  // SIEGE-045: 周期ウェーブタイマーへ渡す結果。
  if (saved) {
    const maxRet = Math.max(...ref.rounds[0].flatMap(b => b.lines.map(l => l.ret)));
    if (saved.periodSec !== ref.cycle) fail("SIEGE-045", `periodSec${saved.periodSec}、期待${ref.cycle}`);
    if (saved.maxSec !== maxRet) fail("SIEGE-045", `maxSec${saved.maxSec}、期待${maxRet}`);
    if (saved.rawText !== output) fail("SIEGE-045", "rawTextが1周目の出力と違う");
  }

  return violations;
}

module.exports = { parseOutput, parseReference, checkProperties, expectedMarch, toSeconds };
