# Trace format v1

UTF-8 JSON Lines。先頭は`meta`、連番`seq`は1から始まります。
各行に `kind`, `line` があり、`line`は同梱Javaソース中の計測呼び出し位置です。
読み込むだけでコードを実行することはありません。最大5 MB・20,000イベントです。

| kind | 必須データ | 意味 |
|---|---|---|
| meta | schema=1, lesson, variant, input | シナリオ。runnerがsource_sha256、producerを付加 |
| new | id, type, fields | 登録した実オブジェクトと、その時点のフィールド |
| set | id, field, value | フィールド更新後の観測値 |
| call | from, to, method, arg | 呼び出し直前の計測 |
| return | from, value | 呼び出しから戻った後の計測 |
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

判定器は`variant`を正解ラベルとして使いません。評価スクリプトだけが、あらかじめ定めた実験ラベルとして使います。
現在の契約は同梱オブジェクトIDと教材操作名に依存するため、一般的なパターン適合性判定器ではありません。
