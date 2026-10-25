"use strict";
// 集結タイムライン計算の出力テキストだけから、計算結果が満たす性質C1〜C10を判定する。
// 性質の定義はdocs/requirements/web-tools/siege-timeline.mdの「計算結果が満たす性質」にある。
// 計算の実装を読まず、出力された時刻と入力の役割だけを使う。

const toSeconds = text => {
  const matched = text.match(/^(\d+)分(\d+)秒$/);
  if (!matched) throw new Error("時刻ではありません: " + text);
  return Number(matched[1]) * 60 + Number(matched[2]);
};

const CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳";

const LINE_RE =/^(\d+分\d+秒) → (.+?)（.+?集結）※行軍(-?[\d.]+)秒（(\d+分\d+秒)着、(\d+分\d+秒)帰還）$/;

// 「参考：2周分の計算結果」を {rounds: [[{name, lines}]], cycle} へ分解する。
function parseReference(text) {
  const rounds = [];
  let round = null;
  let pattern = null;
  let cycle = null;
  for (const line of text.split("\n")) {
    let matched;
    if ((matched = line.match(/^【(\d+)周目】$/))) {
      round = [];
      rounds.push(round);
    } else if ((matched = line.match(/^周期：(.+)$/))) {
      cycle = toSeconds(matched[1]);
    } else if ((matched = line.match(LINE_RE))) {
      pattern.lines.push({
        launch: toSeconds(matched[1]),
        label: matched[2],
        arrival: toSeconds(matched[4]),
        ret: toSeconds(matched[5]),
      });
    } else if (line.endsWith("→メイン→増援")) {
      pattern = { header: line, lines: [] };
      round.push(pattern);
    } else if (line.trim()) {
      throw new Error("解析できない行: " + line);
    }
  }
  return { rounds, cycle };
}

// 違反した性質の名前と理由の一覧を返す。空なら全性質を満たす。
function checkProperties(testCase, output, reference) {
  const { settings, members } = testCase;
  const violations = [];
  const fail = (name, detail) => violations.push(`${name}: ${detail}`);

  if (/-\d|NaN/.test(reference)) {
    fail("C1", "負の時刻またはNaN");
    return violations;
  }
  const { rounds, cycle } = parseReference(reference);
  if (rounds.length !== 2) {
    fail("形式", `周の数が${rounds.length}`);
    return violations;
  }
  if (cycle === null) {
    fail("形式", "周期の行がない");
    return violations;
  }
  // C9: 入力どおりのパターン数で、各パターンは定義順の名前、削りのラベル、
  // 削り→メイン→増援の順の行を持つ（SIEGE-018、SIEGE-020、SIEGE-024）。
  // 入力の入れ替え漏れや行の欠落を、時刻の性質より先に検出する。
  const labelsOf = role => members.filter(m => m[0] === role).map(m => m[1]);
  rounds.forEach((round, r) => {
    if (round.length !== testCase.patterns.length) {
      fail("C9", `${r + 1}周目のパターン数${round.length}、入力${testCase.patterns.length}`);
      return;
    }
    round.forEach((p, i) => {
      const kezuri = labelsOf("削り").filter(label => testCase.patterns[i].includes(label));
      const header = `${CIRCLED[i]}${kezuri.join("+")}→メイン→増援`;
      if (p.header !== header) fail("C9", `${r + 1}周目の見出し${p.header}、期待${header}`);
      const expected = [...kezuri, ...labelsOf("メイン"), ...labelsOf("増援")].join(",");
      const actual = p.lines.map(l => l.label).join(",");
      if (actual !== expected) fail("C9", `${r + 1}周目${p.header}の行${actual}、期待${expected}`);
    });
  });
  if (violations.length) return violations;

  const role = Object.fromEntries(members.map(([r, label]) => [label, r]));
  const rally = { 削り: settings.kz * 60, メイン: settings.mr * 60, 増援: settings.mr * 60 };
  const offset = { 削り: 0, メイン: settings.gap, 増援: 2 * settings.gap };
  // 削りを選んでいないパターン（SIEGE-003）は、メインの着弾 - フェーズ間隔をTとする（SIEGE-014）。
  const T = rounds.map(round => round.map(p => {
    const kezuri = p.lines.filter(l => role[l.label] === "削り").map(l => l.arrival);
    if (kezuri.length) return Math.min(...kezuri);
    return Math.min(...p.lines.filter(l => role[l.label] === "メイン").map(l => l.arrival)) - settings.gap;
  }));

  rounds.flat().forEach(p => p.lines.forEach(l => {
    if (l.launch < 0) fail("C1", `${l.label}の発起${l.launch}`);
  }));

  // C3: 階段状の着弾。あわせて発起と帰還が集結時間と行軍から求まることも確かめる。
  rounds.forEach((round, r) => round.forEach((p, i) => p.lines.forEach(l => {
    const memberRole = role[l.label];
    const march = members.find(m => m[1] === l.label)[2];
    if (l.arrival !== T[r][i] + offset[memberRole]) fail("C3", `${r + 1}周目${p.header} ${l.label}の着弾`);
    if (l.launch !== l.arrival - rally[memberRole] - march) fail("C3", `${l.label}の発起`);
    if (l.ret !== l.arrival + march) fail("C3", `${l.label}の帰還`);
  })));

  // C10: 1周目の各パターンのTは、前に並ぶ行から求めた使用可能時刻で、SIEGE-012の最大値に等しい。
  // 着弾を必要以上に遅らせる退行は、C1〜C9をすべて満たしたままになるため、ここで検出する。
  const ready = {};
  rounds[0].forEach((p, i) => {
    const candidates = [0];
    p.lines.forEach(l => {
      const memberRole = role[l.label];
      const march = members.find(m => m[1] === l.label)[2];
      const lead = { 削り: 0, メイン: settings.gap, 増援: 2 * settings.gap }[memberRole];
      candidates.push((ready[l.label] || 0) + rally[memberRole] + march - lead);
    });
    const expected = Math.max(...candidates);
    if (T[0][i] !== expected) fail("C10", `1周目${p.header}のT${T[0][i]}、最小値${expected}`);
    p.lines.forEach(l => { ready[l.label] = l.ret + settings.buf; });
  });

  // C2: 2周分を通して、同じ人の次の発起が前回の帰還+バッファ以降。
  const uses = {};
  rounds.flat().forEach(p => p.lines.forEach(l => (uses[l.label] ||= []).push(l)));
  Object.entries(uses).forEach(([label, list]) => {
    list.sort((a, b) => a.launch - b.launch);
    for (let k = 1; k < list.length; k++) {
      if (list[k].launch < list[k - 1].ret + settings.buf) {
        fail("C2", `${label}: 発起${list[k].launch} < 帰還${list[k - 1].ret}+${settings.buf}`);
        break;
      }
    }
  });

  // C4: 1周目と2周目でパターンの着弾の順番が同じ。
  const order = ts => ts.map((t, i) => [t, i]).sort((a, b) => a[0] - b[0] || a[1] - b[1]).map(x => x[1]).join(",");
  if (order(T[0]) !== order(T[1])) fail("C4", `${order(T[0])} / ${order(T[1])}`);

  // C5: どのパターンも、2周目と1周目の差が表示された周期と一致する。
  if (T[0].some((t, i) => T[1][i] - t !== cycle)) {
    fail("C5", `周期${cycle}、各差${T[0].map((t, i) => T[1][i] - t).join(",")}`);
  }

  // C6: 1周目を周期ずつずらして繰り返しても、全員が帰還+バッファ以降に次の発起をする。
  const first = {};
  rounds[0].forEach(p => p.lines.forEach(l => (first[l.label] ||= []).push(l)));
  let required = T[0][T[0].length - 1] - T[0][0];
  Object.entries(first).forEach(([label, list]) => {
    const earliest = Math.min(...list.map(l => l.launch));
    const free = Math.max(...list.map(l => l.ret + settings.buf));
    required = Math.max(required, free - earliest);
    if (earliest + cycle < free) fail("C6", `${label}: 次の周の発起${earliest + cycle} < 解禁${free}`);
  });

  // C7: 周期はC6とパターンの順番を守る最小の値。
  if (cycle !== required) fail("C7", `周期${cycle}、最小値${required}`);

  // C8: 「計算結果（1周目）」は参考の1周目と同じ本文に周期の行を付けたもの。
  const firstBlock = reference.split("\n【2周目】\n")[0].replace(/^【1周目】\n/, "");
  const cycleLine = reference.split("\n").filter(l => l.startsWith("周期：")).pop();
  if (output !== `${firstBlock}\n${cycleLine}`) fail("C8", "1周目の出力が参考の1周目と一致しない");

  return violations;
}

module.exports = { parseReference, checkProperties, toSeconds };
