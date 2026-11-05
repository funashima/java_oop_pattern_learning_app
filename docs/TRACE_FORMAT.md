# Trace format v1 / v2

UTF-8 JSON Lines。先頭は`meta`、連番`seq`は1から始まります。
各行に `kind`, `line` があり、`line`は同梱Javaソース中の計測呼び出し位置です。
読み込むだけでコードを実行することはありません。最大5 MB・20,000イベントです。

| kind | 必須データ | 意味 |
|---|---|---|
| meta | schema=1または2, lesson, variant, input | シナリオ。runnerがsource_sha256、producerを付加 |
| new | id, type, fields | 登録した実オブジェクトと、その時点のフィールド |
| set | id, field, value | フィールド更新後の観測値 |
| call | from, to, method, arg | 教材上の操作開始の手動計測。通常はメソッド呼び出し直前 |
| return | from, value | 操作終了時の観測値。Javaの戻り値とは限らない |
| exception（v2のみ） | from, error="ParseError" | 復号のNumberFormatExceptionを正規化した操作終了 |
| checkpoint | name, observed | Javaの登録済み実オブジェクトを直接読み取った状態 |
| cycle_begin | cycle, members, input | Observer通知前の登録先 |
| cycle_end | cycle | 通知ループ終了 |
| result | value | Javaが出力する業務結果 |
| end | complete=true | 記録終了 |

フィールド値: null、真偽値、整数、文字列、`{"ref":"object_id"}`、それらの配列。
パイロットで数値演算するフィールドはJava intです。JSONの一般数値からJava型を推論しません。
動的型は`new.type`、宣言型の補助表示は`lessons/*.json`の注釈です。
循環参照はIDで表せますが、任意のJavaオブジェクトを自動列挙する機能はありません。

`checkpoint.observed`は `{id: {type, fields}}` です。再生器はこれを**状態更新には使わず**、`new`と`set`で再構成した状態の照合にのみ使います。
ただし生成時の初期値と照合時の値変換器はJava側で共有するため、完全に独立な二実装ではありません。

## 操作・観測境界の意味

`new`は計測器への実オブジェクトの登録です。JVMの割当て時点や、Factoryが毎回新しい実体を生成したことを保証しません。
`set`は更新後のフィールド値を記録します。`return`自体はフィールド更新イベントの代わりにはなりません。

| 教材 | call / returnの解釈 |
|---|---|
| 参照 | `write`はフィールド代入を表す教材上の操作名。`Box.write`というJavaメソッドは存在しない。終了値は代入後のvalue |
| Strategy | `quote`は実メソッド呼び出し。終了値は料金の計算結果 |
| State | `handle`はvoidメソッド。終了値は通過回数passed。`call.arg=0`は固定値で、要求先nextを記録していない |
| Observer | `update`はvoidメソッド。終了値は通知値で、Javaの戻り値ではない |
| Abstract Factory | 製品取得の戻り参照、encodeの戻り文字列、decodeの戻り整数、または限定した例外を記録 |

再構成状態と実状態の一致を確認するのは、教材で選んだ**同期後のcheckpoint**です。
例えばStrategyでは、実オブジェクトのtotal更新後にreturnを記録し、その後にsetを記録します。
このreturnとsetの間では、実オブジェクトと再構成状態のtotalが一致しない場合があります。
全イベント位置で状態一致が成立するという仕様ではありません。
この境界例は基準版を対象とするA8で再現できます。

直接観測は登録済みオブジェクトについて取得できるフィールドに限ります。
任意のローカル変数・スタック・全継承フィールドを観測するものではなく、
手動計測が実際の引数や受信者を常に忠実に記録したことも、checkpoint一致だけでは保証できません。

## schema 1とschema 2の保証範囲

| 項目 | schema 1：既存4教材 | schema 2：Abstract Factory |
|---|---|---|
| call / returnのpayload | 整数 | フィールド値と同じ領域。文字列・参照・nullを含む |
| callと終了の対応 | 一般的な対応検査を行わない | 同じ受信者のreturn / exceptionとの対応を検査。ネスト非対応 |
| 履歴を使う契約 | 教材別に定めた受信者・通知回数等 | 製品取得元・戻り参照・保持参照、encode→decodeのデータの対応等 |
| 例外 | 一般的な例外記録の仕様はない | 復号のNumberFormatExceptionをParseErrorへ正規化する範囲のみ |

schema 1の契約PASSを、引数を含む全履歴の忠実性の保証と解釈しないでください。
A3ではObserverのログ上の引数だけを変更しても状態照合と契約がともにPASSとなります。
A4の通知順の変更もPASSですが、こちらは現在の契約が順序を要求しないためです。
両者は区別して扱います。[再現手順](REPRODUCIBILITY.md)に対象コミットと期待判定を記載しています。

判定器は`variant`を正解ラベルとして使いません。評価スクリプトだけが、あらかじめ定めた実験ラベルとして使います。
現在の契約は同梱オブジェクトIDと教材操作名に依存するため、一般的なパターン適合性判定器ではありません。

## Abstract Factoryのschema 2

既存4教材はschema 1の整数payloadを維持します。Abstract Factoryだけがschema 2を使います。
`call.arg`と`return.value`にフィールド値と同じ値領域を使い、生成操作の引数なしをnull、戻り製品を`{"ref":"id"}`、符号化結果を文字列で表します。登録前のID参照は拒否します。
各`call`は同じ受信者の`return`または`exception`で閉じます。ネスト、対応しない終了、未完了呼び出しのある`end`は拒否します。途中で切れた記録は読込可能ですが教材契約はUNKNOWNです。
任意のJava例外を扱う機能ではありません。比較例の復号で発生するNumberFormatExceptionだけをParseErrorへ対応付けます。例外時のdecodedはnullであり、0への代替ではありません。

1. decimal_products → decimal_encoded → decimal_decoded
2. hex_products → hex_encoded → hex_decoded

製品取得の呼出し先・戻り参照・Clientの保持参照を照合します。
encodeの入力と戻り文字列、decodeに渡した文字列、戻り値／ParseErrorと結果フィールドの対応も別に検査します。
さらに系列の注釈、指定系列の正準表現、当該入力での往復変換を別々に判定します。
この限定した履歴検査を既存4教材へ遡って適用してはいません。
source_sha256不一致時の行強調無効化は両版に共通です。
