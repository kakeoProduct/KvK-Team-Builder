# 要件定義: 個人名を含むデータの保持形式

実運用の参加者名を含むデータを、バージョン管理の対象外に保持するときの置き場所と形式を定める（ROS-055、
ADR 0027）。Repositoryには本書の形式と架空の例だけを置き、実際の値は置かない。例の名前、同盟、ID、
数値はすべて架空で、既定値ではない。置き場所、ファイル形式、列とキーの名前は作成者が決めた（作成者の仮定A-23）。

## 1. 置き場所と共通の規則

| ID | 分類 | 要件 |
|---|---|---|
| DAT-001 | 非機能 | 個人名を含むデータは、イベントごとのフォルダにまとめて置く。既定はメインの作業ツリーの`tmp/events/<開催日>-<イベント名>/`（`.gitignore`の`/tmp/`の対象）とし、運用者はRepositoryの外のフォルダを指定してもよい。アプリはイベントのフォルダをパスで受け取り、イベント名から作らない。Session用のworktreeの`tmp/`には置かない（worktreeを削除すると消えるため）。コミット、Pull Request、Issue、レビュー結果へ実際の値を転記しない（ADR 0024）。検証は、`.gitignore`が`/tmp/`を対象にしていることを構造テスト（`tests/test_ai_harness.py`）で確かめる |
| DAT-002 | 非機能 | イベントのフォルダのテキストファイル（`roster.txt`、CSV、`settings.json`）はUTF-8とする。書き出しはBOMなしとし、読み込みはBOMの有無の両方を受け付け、UTF-8として読めないファイルはファイル名と行を示して入力のエラーとする（作成者の仮定A-23）。表形式のデータはCSVとし、1行目に列名を書く。列名は本書の英語の識別子を使う。取得時刻などの時刻の値（`fetched_at`、`checked_at`、`roster_received_at`）は時差付きのISO 8601で書く。時差のない時刻は、ファイル名と行（JSONではキー）を示して入力のエラーとする。`power_snapshot.csv`と`alliance_roster.csv`のそれぞれの中で（`alliance_roster.csv`は同じ同盟の中で）、照合した結果（A-29のまとまりを含む）が同じメンバーの行が同じ取得時刻で2行以上ある場合も同じとする。`alliance_roster.csv`で同盟の違う行に同じメンバーが同じ取得時刻で載る場合も、所属を決められないため同じとする。取得時刻が違えば、最も新しい行の同盟の名簿にだけ数える。`game_id`が空欄の行は、名前の対応表で`game_id`を補ってから同じメンバーかを決め、補えなければ、同じ同盟の中だけで`game_name`が同じIDのない行どうしを同じメンバーとし、IDのある行とのまとめ方はA-29による。照合の件数も、このまとまりで数える（旧Q-123、作成者の仮定A-29）。`name_map.csv`は、1人の別名で同じ`game_id`の行が複数あってよく、`roster_name`のある行で同じ`roster_name`と`alliance`が別の`game_id`を指す場合と、`roster_name`が空欄の行で同じ`game_name`と`alliance`が別の`game_id`を指す場合だけを入力のエラーとする。同じ`roster_name`と`alliance`で`game_id`のある行と空欄の行が並ぶ場合はエラーにせず、A-29でまとめた結果に従う。1つのまとまりになれば照合でき、2つ以上のまとまりに当たれば照合できないとして確認に回す（作成者の仮定A-28）。どの取得元のデータにも、取得元と取得時刻の列を持たせる |
| DAT-003 | 非機能 | 取得元は`external_site`（外部の集計サイト）、`screenshot`（スクリーンショットからの読み取り）、`manual`（運用者の入力）のいずれかで書く。外部の集計サイトが使えなくなっても、ほかの2つの取得元で同じ形式のデータを作れるようにする（ROS-051、ROS-053）。ゲーム内のIDが分からない場合は`game_id`を空欄にしてよく（`power_snapshot.csv`と`alliance_roster.csv`の`external_site`の行を除く。DAT-006。名前の対応表の行は取得元によらず空欄にしてよい。作成者の仮定A-26）、ゲーム内名は変わり得て一意ではなくなるため（旧Q-126）、名前の対応表（Git管理外）で今のIDと対応させるのを原則とし（旧Q-123）、補えないメンバーは作成者の仮定A-29で照合し、2件以上に当たって1人に決まらなければROS-060で確認に回す（0件の扱いは作成者の仮定A-28） |

## 2. 入力データ

| ID | 分類 | 要件 |
|---|---|---|
| DAT-004 | 入力正規化 | 参加者一覧は、運用者から受け取ったテキストのまま`roster.txt`に保存する。書き方はROS-001〜ROS-033に従う |
| DAT-005 | 入力正規化 | 名前の対応表（ROS-006）は`name_map.csv`とし、列は`roster_name`（参加者一覧の記載）、`game_name`（ゲーム内名）、`game_id`（ゲーム内のID）、`alliance`（参加者一覧の同盟）、`source`、`checked_at`とする。編成に参加しないメンバーの今のIDを持つため、`roster_name`を空欄にした行を書いてよい。その行の`alliance`は、確かめた時点のゲーム内の同盟とする（旧Q-123、作成者の仮定A-29）。このファイルはイベントのフォルダに置き、次のイベントでは前回のファイルを写して直す |
| DAT-006 | 入力正規化 | 総力とMystic Trialは`power_snapshot.csv`とし、列は`game_id`、`game_name`、`alliance`、`power`（総力。整数。未取得は空欄）、`mystic_trial`（Mystic Trialのスコア。未取得は空欄）、`source`、`fetched_at`とする。同盟の名簿（ROS-054）は`alliance_roster.csv`とし、列は`alliance`、`game_id`、`game_name`、`power`（未取得は空欄）、`source`、`fetched_at`とする。編成に参加しないメンバーも1行ずつ含める。外部の集計サイトのアダプターは、取得を指示した範囲（取得の単位）のデータをすべて取得できたときだけファイルを書く。取得の単位は、同盟の名簿では同盟、総力とMystic Trialでは同盟か順位表の上位N人とする。通信の失敗、応答の途中切れ、ページの欠けは一部だけの取得とし、ファイルを書かずにROS-053に従って止める。同盟の単位で0行の応答と、0行の順位表と、取得元が一覧の終わりを示さずにN人未満で終わった順位表も、一部だけの取得とする。同盟を移った人が、移った先の同盟を取り直すまで総力の未取得になることは許す（旧Q-124）。外部の集計サイトの名簿の行は`game_id`が欠けない（旧Q-127）。総力のデータの`external_site`の行も欠けないとみなし（順位表の応答は保持しているデータのとおり。旧Q-128）、`source`が`external_site`の行で`game_id`が空欄なら、取得の誤りとしてファイルを書かずに止める。手で直したファイルを読むときも、`external_site`の行で`game_id`が空欄なら、ファイル名と行を示して入力のエラーとする。止めた後の扱いはROS-053の取得の失敗と同じとする（作成者の仮定A-26）。取得元に記録がないメンバーは一部だけの取得に当たらず、行を書かずに未取得とする（作成者の仮定A-26）。新しいファイルは、取得した行と、置き換える前のファイルにある単位の外の行から作る。単位の中の前の行（`alliance_roster.csv`では取得した同盟の行すべて、`power_snapshot.csv`では、同盟で取得したならその同盟の、順位表で取得したならすべての同盟の`source`が`external_site`の行）は引き継がず、それ以外の行は書き換えずにそのまま残す。書くときに同じメンバーの行をまとめない。アダプターは行を取得元、取得時刻、ファイル名と行とともに不変な値として渡し、1人1つの値はドメインでROS-050とA-28により決める。複数のファイルの置き換えが途中で失敗しても、新しいファイルと古いファイルを混ぜて編成に使わず、ファイル名を示して止める。置き換えが失敗した後でも、同じ単位の取り直しに成功すれば、その結果を編成に使える。置き換えの方法（一時ファイル、退避、戻し）は実装Issueの7のADRで決める（作成者の仮定A-26）。行がないメンバーは未取得として扱うため、途中で切れたファイルを正常なデータとして残さない |
| DAT-007 | 運用操作 | 個人名を含む運用者の指定は`settings.json`とする。メンバーは`{"name": 参加者一覧の名前, "alliance": 参加者一覧の同盟}`の形で指す。同盟は`alliance_choices`を当てる前の、参加者一覧に書かれた同盟とする（作成者の仮定A-28）。キーは`leaders`（リーダーの順の一覧）、`pin_team`（メンバーと隊の番号の組の一覧、FRM-076(1)）、`force_wait`と`optional_wait`（メンバーの一覧、FRM-076(2)(3)）、`apart_pairs`（2人の組の一覧、FRM-105）、`destination_overrides`（メンバーと移動先の同盟の組の一覧、FRM-101(1)）、`alliance_choices`（ROS-053の確認で運用者が選んだ同盟。メンバーと同盟の組の一覧、作成者の仮定A-28）とする。ほかの設定値（戦闘時間、人数の上限、グループ、協力者同盟、移動先が分かれてよい同盟、総力の目標など）の置き場所は実装Issueの1と2で決め、それまでは同じファイルに置いてもよい。その場合の形は4章の例による。参加者一覧を受け取った時刻は`roster_received_at`（時差付きのISO 8601）とし、参加者一覧の記載の総力を使う場合（ROS-050）に必須とする（作成者の仮定A-27）。協力者の欄の協力者の移動先（FRM-087）は、`{"alliance": 参加者一覧の同盟, "destination_alliance": 移動先の同盟}`の一覧の`cooperator_destinations`とする。書ける値と誤りの扱いは作成者の仮定A-28による。協力者同盟（ROS-007）は1件だけの`cooperator_alliance`とし、グループの隊は`{"first": 最初の隊, "last": 最後の隊}`の範囲で書く |

## 3. 出力データ

| ID | 分類 | 要件 |
|---|---|---|
| DAT-008 | 表示のみ | 編成結果とチャット共有用テキストは、イベントのフォルダの`output/`に置く。グループがある総力モードでは、チャット共有用テキストを2つのファイルに分ける。通常モードとグループのない総力モードでは隊のファイルだけを書き、隊の一覧はそのモードの形（通常モードはOUT-001〜OUT-004、総力モードはOUT-015）とする（作成者の仮定A-23）。隊のファイルには、グループのない総力モードの総力の取得元と取得日の行（OUT-015）、隊ごとの一覧（そのモードの形）、OUT-006の注記、警告（OUT-011。FRM-049を含み、FRM-106を除く）、別枠・待機・登録のみ（OUT-009）、書く先のない注記の「注記:」の行（OUT-007）、治療時間の目安（OUT-005。グループがある総力モードだけ）、同盟メンバー表（OUT-014。総力モードで出すかはQ-108による）を入れる。同盟移動のファイルには、同盟移動（OUT-016）、グループの登録（OUT-017）、入出の人数と総力（OUT-018。FRM-106の警告を含む）を入れる |

## 4. 架空の例

`tmp/events/2026-01-01-example/`の例を示す。数値は運用値と関係のない架空の値である。形を示すための一部の行だけで、`roster.txt`と`alliance_roster.csv`（移動先の同盟AAAとBBBの名簿）は省く。ハナは参加者一覧ではDDDのブロックにいるが、総力のデータではAAAにいるため確認に回り、運用者が`alliance_choices`でAAAを選んだ例である。省いた`roster.txt`には、協力者同盟CCCのブロックと、DDDのブロックの協力者の欄があるものとする。省いたBBBの名簿のミナの行も、`source`が`screenshot`、`game_name`が`みな☆`で`game_id`が空欄とする。省いたAAAの名簿にはユウ（100000001）、ソラ、カイの行が、BBBの名簿にはレンの行があるものとする。

`name_map.csv`

```csv
roster_name,game_name,game_id,alliance,source,checked_at
ユウ,Yuu_01,100000001,AAA,external_site,2026-01-01T12:00:00+09:00
ミナ,みな☆,,BBB,manual,2026-01-01T12:05:00+09:00
ハナ,Hana_03,100000003,DDD,manual,2026-01-01T12:06:00+09:00
```

`power_snapshot.csv`

```csv
game_id,game_name,alliance,power,mystic_trial,source,fetched_at
100000001,Yuu_01,AAA,512300000,2101,external_site,2026-01-01T12:00:00+09:00
,みな☆,BBB,401000000,,screenshot,2026-01-01T12:10:00+09:00
100000003,Hana_03,AAA,388000000,1850,external_site,2026-01-01T12:00:00+09:00
```

`settings.json`（4隊、グループ2つの例）

```json
{
  "battle_start": "20:00",
  "battle_end": "24:30",
  "roster_received_at": "2026-01-01T11:50:00+09:00",
  "leaders": [
    {"name": "ユウ", "alliance": "AAA"},
    {"name": "ミナ", "alliance": "BBB"},
    {"name": "ソラ", "alliance": "AAA"},
    {"name": "リク", "alliance": "DDD"}
  ],
  "groups": [
    {"name": "グループ①", "destination_alliance": "AAA", "teams": {"first": 1, "last": 3}},
    {"name": "グループ②", "destination_alliance": "BBB", "teams": {"first": 4, "last": 4}}
  ],
  "cooperator_alliance": {"alliance": "CCC", "destination_alliance": "BBB"},
  "cooperator_destinations": [{"alliance": "DDD", "destination_alliance": "AAA"}],
  "splittable_alliances": ["DDD"],
  "apart_pairs": [[{"name": "カイ", "alliance": "AAA"}, {"name": "レン", "alliance": "BBB"}]],
  "pin_team": [{"member": {"name": "カイ", "alliance": "AAA"}, "team": 2}],
  "force_wait": [{"name": "レン", "alliance": "BBB"}],
  "alliance_choices": [{"member": {"name": "ハナ", "alliance": "DDD"}, "alliance": "AAA"}],
  "optional_wait": [{"name": "サキ", "alliance": "DDD"}],
  "destination_overrides": [{"member": {"name": "サキ", "alliance": "DDD"}, "destination_alliance": "BBB"}],
  "overcap_limit": 11,
  "group_member_cap": 40,
  "alliance_member_cap": 90,
  "alliance_power_targets": {"BBB": 12000000000}
}
```

`overcap_limit`は、上限超えを許す出撃人数の最大値（FRM-036）である。時刻は`HH:MM`で書き、24時以降は
`24:30`の形（ROS-022）とする。
