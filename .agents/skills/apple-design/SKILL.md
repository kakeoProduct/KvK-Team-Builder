---
name: apple-design
description: Appleのインターフェース設計と流体的で物理的な動きをWebへ適用する。Web UIの新規実装・変更・レビュー、即時フィードバック、ジェスチャー、ばね、半透明マテリアル、文字組み、レスポンシブ対応、アクセシビリティを扱うときに使用する。
---

# Appleの設計原則をWeb UIへ適用する

見た目だけをApple製品へ似せるのではなく、人の思考と操作に沿う予測可能で滑らかな
インターフェースを作る。操作中の現在値、速度、移動方向を保ち、いつでも中断・反転できる
ことを中心に考える。

このリポジトリでは、将来のWeb UIを新規実装、変更、またはレビューするときの基準として
使用する。CLIやMarkdown出力だけの変更では使用しない。UIへKvKの業務判断を複製せず、
`AGENTS.md`と`docs/architecture.md`の依存境界を優先する。

## 最初に目的と状態を整理する

実装前に、画面の主要目的、利用者の最短経路、表示する状態、回復手段を整理する。

- 画面ごとに主要操作を1つ明確にし、詳細設定は必要な場所で段階的に開示する
- 読み込み中、成功、警告、入力エラー、必須条件エラー、空状態を別々に設計する
- 破壊的操作は取り消せる形を優先し、不可逆な場合だけ確認を求める
- 画面は「現在地」「次にできること」「対象内容」「戻り方」を読み取れるようにする
- 同じ見た目、用語、アイコン、配置には同じ意味と挙動を与える
- 操作対象の近くへ、それを変更するControlと説明を置く

KvK Team Builderでは、警告と必須条件エラーを色だけで区別しない。編成中、検証済み、
警告あり、出力不可の状態を、文言、アイコン、見出し、必要に応じて色で重ねて示す。

## 反応を即時にする

直接操作の感覚は入力直後の反応から始まる。

- Buttonは離した時点だけでなく、押した時点で視覚Feedbackを返す
- 不要な待機、Timer、Debounceを入力経路へ置かない
- Drag、Slider、Sheetは操作中もPointerへ1対1で追従させる
- 長い処理は入力を黙って無視せず、進行状態と再実行可否を示す
- 入力検証は送信後にまとめず、確定できる範囲でその場に示す

```css
.button:active {
  transform: scale(0.97);
  transition: transform 100ms ease-out;
}
```

押下FeedbackのScaleは意味のある操作だけへ控えめに使い、Layoutを動かさない。

## 直接操作をPointerへ追従させる

Drag対象は、つかんだ位置のOffsetを保ったままPointerへ追従させる。対象の中心へ瞬時に
吸着させない。

- Pointer Eventsと`setPointerCapture`を使い、要素外へ移動しても追跡する
- 直近数回の位置と時刻を保持し、解放時の速度を計算する
- 約10pxの移動閾値でTapとDragを区別する
- 最初の移動から考えられるGestureを並行評価し、意図が明確になったら不採用候補を止める
- 境界では急停止させず、超過距離に応じて抵抗を増す

```js
element.addEventListener("pointerdown", (event) => {
  element.setPointerCapture(event.pointerId);
  const grabOffset = event.clientY - element.getBoundingClientRect().top;
  // 位置、時刻、grabOffsetを保持して追従と速度計算に使う。
});
```

境界を越えたDragには次のようなRubber Bandを使える。

```js
function rubberband(overshoot, dimension, constant = 0.55) {
  return (
    (overshoot * dimension * constant) /
    (dimension + constant * Math.abs(overshoot))
  );
}
```

## 動きをいつでも中断できるようにする

利用者が触れられるAnimationは、途中でつかみ直し、逆方向へ動かせなければならない。

- Transition中も入力を無効化しない
- 論理上の目標値ではなく、画面上の現在値から次のAnimationを始める
- 反転時は速度を0へ切らず、現在速度を新しい目標へ引き継ぐ
- Gesture駆動の動きへ固定されたCSS `@keyframes`を使わない
- 2次元移動はXとYを独立したSpringとして扱う
- 表示と非表示は同じ経路を往復し、Triggerを起点とする`transform-origin`を使う

CSS Transitionは単純なHover、短いOpacity変化など、操作中につかみ直さない対象に限る。

## Springで振る舞いを表現する

触れられる対象は固定時間のAnimationより、現在値と速度へ応答するSpringを優先する。

- 通常のUIは臨界減衰に近い`damping 1.0`、`response 0.3〜0.4秒`から始める
- FlickやDrag解放など運動量を伴う操作だけ、`damping 0.8`前後の小さなBounceを許す
- Menuの表示など運動量のない操作へBounceを加えない
- 数値は慣例で選ばず、画面録画や低速再生で妥当性を確認する

| 操作 | Damping | Response |
|---|---:|---:|
| 移動・再配置 | `1.0` | `0.4` |
| 回転 | `0.8` | `0.4` |
| Drawer・Sheet | `0.8` | `0.3` |

MotionまたはFramer Motionを使う場合の出発点は次のとおりである。

```js
import { animate } from "motion";

animate(element, { y: 0 }, { type: "spring", bounce: 0, duration: 0.4 });
animate(element, { y: target }, { type: "spring", bounce: 0.2, duration: 0.4 });
```

Library追加は自動的に正当化されない。現在のUI基盤で要求を満たせないことを確認し、
主要依存関係を増やす場合はADRへ理由を残す。

## 速度と運動量を引き継ぐ

Gesture終了後のAnimationは解放時の速度から連続して始める。Libraryが相対速度を要求する
場合は、残り距離で正規化する。

```text
relativeVelocity = gestureVelocity / (targetValue - currentValue)
```

解放地点だけでSnap先を決めず、速度から静止位置を投影して最も近い候補を選ぶ。

```js
function project(initialVelocity, decelerationRate = 0.998) {
  return (
    (initialVelocity / 1000) *
    (decelerationRate / (1 - decelerationRate))
  );
}

const projectedEndpoint = currentPosition + project(releaseVelocity);
const target = nearestSnapPoint(projectedEndpoint);
animateSpringTo(target, { velocity: releaseVelocity });
```

## 空間上の関係を保つ

- 右から現れたPanelは右へ戻すなど、表示と非表示の経路を対称にする
- Popover、Menu、SheetはTriggerとの位置関係が分かる起点から現す
- 中間Frameも最終状態へ向かう方向を伝える
- Modalは背景を暗くしてTaskを分離し、非Blocking Panelは背景を残して流れを保つ
- 親子Sheetを重ねる場合は、親を段階的に暗くし、奥行きを示す

## マテリアルと奥行きを節度を持って使う

半透明は装飾ではなく、浮いている操作層と内容層の階層を伝えるために使う。

- Navigation、Toolbar、Sheetは必要な場合だけ半透明の浮遊層にする
- 大きいSurfaceは小さいChipより強いBlurとShadowで厚みを示す
- 淡い半透明Surface同士を重ねない
- 変化する背景上の文字はContrastとWeightを高め、可読性を守る
- 固い区切り線より、内容がChromeの下へ入る位置だけScroll Edge効果を使う
- Glass SurfaceはOpacityだけでなくBlurとScaleを合わせて出入りさせる

```css
.toolbar {
  background: rgb(255 255 255 / 60%);
  backdrop-filter: blur(20px) saturate(180%);
  border-top: 1px solid rgb(255 255 255 / 40%);
}
```

透明度を使う前に、文字、状態、表の読み取りやすさを実機相当の背景で確認する。

## 文字組みで階層を作る

- 既定はPlatformのSystem Fontとする
- 大きい見出しはTrackingを狭め、本文は0付近、小さい文字は必要に応じて少し広げる
- 大きい見出しはLeadingを狭め、本文は読みやすく広げる
- SizeだけでなくWeight、Size、Leadingの組合せで階層を作る
- 間隔を`rem`や`em`で設計し、利用者の文字拡大でLayoutが壊れないようにする
- 日本語では英語用の負のTrackingを機械的に適用せず、実際の文字列で確認する

```css
:root {
  font: 100%/1.5 system-ui, sans-serif;
}

.display {
  font-size: clamp(2rem, 5vw, 4rem);
  line-height: 1.05;
  letter-spacing: -0.02em;
  font-optical-sizing: auto;
}
```

## アクセシビリティを同じComponentへ組み込む

低モーションはFeedbackを消す指定ではない。大きな移動やBounceを、短いCross Fadeや静的な
状態変化へ置き換える。

```css
@media (prefers-reduced-motion: reduce) {
  .sheet {
    transition: opacity 200ms ease;
    transform: none !important;
  }
}

@media (prefers-reduced-transparency: reduce) {
  .toolbar {
    background: white;
    backdrop-filter: none;
  }
}

@media (prefers-contrast: more) {
  .toolbar {
    background: Canvas;
    border: 1px solid CanvasText;
  }
}
```

次も同じ変更内で確認する。

- Keyboardだけで到達、操作、取消、送信できる
- Focus Indicatorが見え、ModalやSheetのFocus移動と復帰が自然である
- Status、Warning、ErrorがScreen Readerへ伝わる
- 色だけに依存せず、十分なContrastと意味のあるLabelがある
- Touch Targetが十分に大きく、誤操作を取消できる
- Mobile、Desktop、文字拡大、Light／Darkで主要経路が成立する

## 8つの原則で判断を説明する

設計の理由を次の言葉で説明する。

1. **目的**: 利用者の時間、注意、信頼を使う価値がある要素だけを作る
2. **主体性**: 選択、取消、回復を用意し、利用者が制御できるようにする
3. **責任**: Privacyと安全を守り、必要な情報だけを適切な時点で求める
4. **親しみやすさ**: Platform慣習と既知のMental Modelを尊重する
5. **柔軟性**: Device、入力方法、能力、習熟度の違いへ適応する
6. **単純さ**: 見た目の最小化ではなく、主要経路の理解と操作を簡単にする
7. **作り込み**: Typography、色、配置、Timingを意図を持って揃える
8. **喜び**: 他の7原則を満たした結果として、落ち着きと自信を生む

## 実装とレビューの手順

1. `AGENTS.md`、`README.md`、`docs/architecture.md`、対象UIとテストを読む。
2. 主要経路と、読み込み、成功、警告、入力エラー、出力不可の状態を列挙する。
3. 追加する視覚要素と動きが、8原則のどれに寄与するか説明する。
4. まず動作するPrototypeでInteractionとVisualを同時に確認する。
5. Pointer追従、割り込み、速度継承、表示／非表示の経路を実際に操作する。
6. Keyboard、Focus、文字拡大、低モーション、低透明度、高Contrastを確認する。
7. MobileとDesktopで主要経路を確認し、Animationは録画の低速再生でも確認する。
8. `python tools/check.py`を実行し、変更したUIの視覚確認方法と残る制約を報告する。

Streamlitなど基盤側に制限がある場合、無理なGestureや装飾用JavaScriptを追加しない。
目的、即時Feedback、明確な状態、Keyboard操作、読みやすいTypographyを優先し、実現できない
Interactionは制約として報告する。

## 出典とライセンス

このスキルはEmil Kowalskiによる
[`apple-design`](https://github.com/emilkowalski/skills/tree/main/skills/apple-design)を
2026-07-20に取得し、このリポジトリ向けに日本語化・補足したものである。基準にした上流の
最新Commitは`56de6f5d6642f761b5e17629fccf53e303b3da9b`である。原著作物の条件は同じDirectoryの
`LICENSE`を参照する。
