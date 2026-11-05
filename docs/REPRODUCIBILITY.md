# 再現手順と検証対象

紀要論文の数値は、次の異なる実験から得られています。対象版を混ぜずに再現してください。
ここに示す件数は有限の教材・入力・観測境界に対する結果であり、未知誤りの検出率や学習効果ではありません。

## 結果と実装の対応

| 検証 | 実行対象 | 保存結果 | 確認する値 |
|---|---|---|---|
| 基準版4教材 | `a92f4705f968d753952adaa7f5398e38c81d6a85` | `verification/semantic/baseline/summary.json` | 26シナリオ、86チェックポイント、正常13・比較13 |
| 境界例A1〜A8 | 同じ基準コミット | `verification/semantic/audit_results/audit_results.json` | 下表の8組の判定 |
| 5教材版 | `b263bea1921884729a3b77e6a81cd6e99031742f` のアプリ実装 | `results/five_lessons_live/summary.json` | 36シナリオ、146チェックポイント、正常18・比較18 |
| 統合Factory教材 | 同じ5教材版 | `results/factory_sweep.json` | 512シナリオ、3072チェックポイント |
| 独立Java/Python実装 | `verification/semantic/cross_language/` 内のソース | 同フォルダの `results/summary.json` | 1280組の入力別観測、256組の系列変換が言語間で一致 |

5教材版の正常・比較は、観測整合性がともにPASS、教材契約がそれぞれPASS・FAILとなることを確認します。
統合Factory比較例のHex段階は、往復一致10件・値の不一致90件・ParseError 156件です。
系列整合は全256入力でFAILとなります。
独立比較の一致は、誤った実装同士の一致も含み、仕様適合そのものを意味しません。

| 境界例 | 変更・比較 | 観測整合性 | 教材契約 |
|---|---|---|---|
| A1 | Strategy入力0：正常・比較の全チェックポイントと最終値が一致 | PASS | FAIL（比較例） |
| A2 | Discount宛てcallを記録から除く | PASS | FAIL |
| A3 | Observerの記録上の引数だけを変更 | PASS | PASS |
| A4 | Observerの通知順を逆転 | PASS | PASS |
| A5 | 参照教材のvalue更新のsetを記録から除く | FAIL | PASS |
| A6 | 直接観測のtotalだけを改変 | FAIL | PASS |
| A7 | endを除く | PASS | UNKNOWN |
| A8 | Strategyのreturn直後・set前へチェックポイントを追加 | FAIL（2か所） | PASS |

A2・A5・A6・A7は保存記録の変更、A3・A4・A8は一時コピーしたJavaソースの変更です。
A1は入力0での実行比較です。A3は未検査の情報、A4は契約が要求しない順序の例であり、
同じPASS/PASSでも意味が異なります。スクリプトが成功することは、この期待結果の再現を意味します。

## 環境

Python 3.10以降とJDK 17以降を使用します。GUI以外はPythonの標準ライブラリで動きます。
Javaのコンパイラ機能を使うためJREだけでなくJDKを用意してください。
以下はLinux / bashを想定し、更新済みリポジトリのルートから実行します。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python --version
java --version
python -c 'from PyQt6.QtCore import PYQT_VERSION_STR, QT_VERSION_STR; print("PyQt", PYQT_VERSION_STR, "Qt", QT_VERSION_STR)'
mkdir -p results/rerun
```

保存された5教材版の試験はPython 3.12.14、JDK 17.0.20、PyQt6/Qt 6.12.0です。
`requirements.txt` は許容範囲の指定であり、この保存環境を固定するものではありません。
再実行した環境の版を結果と併せて記録してください。
`results/rerun/` はGit管理から除外し、以下のコマンドは保存済みの原結果を上書きしません。

## 5教材版

```bash
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
python evaluate.py --out results/rerun/bundled
python evaluate.py --live --out results/rerun/five_lessons_live
python evaluate_factory.py --out results/rerun/factory_sweep.json
```

全29試験のうち、コア等は24件、GUIは5件です。PyQt6がなければGUI5件はスキップされます。
`OK (skipped=5)` を29件成功として報告しないでください。
同梱記録の再評価は10記録、`--live` は36シナリオです。

## 基準版とA1〜A8

**A1〜A8は、更新済み5教材版を引数に渡さず、基準コミットの別作業ツリーに対して実行します。**
未使用の作業先 `../java_oop_pattern_learning_app-a92f470` を使用します。
同名の作業先が既にある場合はそのHEADを確認するか、別名に置き換えてください。

```bash
git worktree add --detach ../java_oop_pattern_learning_app-a92f470 a92f4705f968d753952adaa7f5398e38c81d6a85
git -C ../java_oop_pattern_learning_app-a92f470 rev-parse HEAD
python ../java_oop_pattern_learning_app-a92f470/evaluate.py --live --out results/rerun/baseline
python verification/semantic/semantic_audit.py ../java_oop_pattern_learning_app-a92f470 results/rerun/audit
```

浅いcloneで基準コミットが見つからない場合は、履歴を取得してから実行してください。
`git rev-parse --is-shallow-repository` が `true` なら `git fetch --unshallow origin` で取得できます。
スクリプト内のassertを有効にするため、Pythonの `-O` オプションは使いません。
元のスクリプトは対象版を強制しないので、上記のHEAD確認は省略しないでください。

## 独立した言語間比較

```bash
python verification/semantic/cross_language/run_study.py --output results/rerun/cross_language
```

これはGUIのPython再生器を実行する試験ではありません。
JavaとPythonの独立Codec実装に、0〜255の入力と5構成を与えて比較します。
NumberFormatExceptionとValueErrorをParseErrorへ正規化した入力別観測と、Decimal→Hexの再符号化を照合します。
元の例外名もJSON Linesへ保存します。任意文字列やヒープ・並行性の同値を証明するものではありません。

## ソースの識別と保存結果の保全

`java/PatternPilot.java` のSHA-256は次のとおりです。

| 版 | SHA-256 |
|---|---|
| 基準版 | `c909c0c560ec78ccfd82d451a862a201b8352cd93711aad1dfbf88944270aef0` |
| 5教材版 | `500c3527ddb2545933dcf8562bee3f0cec0f3072ee21230b05fbcc7345f07578` |

今回の資料追加・整理ではアプリ実装と同梱トレースを変更していません。
`verification/semantic/` は元の再現資料の内容を保持しています。
`results/test_log.txt` や `verification/semantic/core_tests.txt` 等の実験ログも保持しています。
実行時間やプラットフォーム文字列は環境依存なので、再実行結果のファイル全体が元データと同じハッシュになるとは限りません。
比較する対象は上記の判定・件数・入力別観測です。

```bash
python tools/update_manifest.py --check
```

`MANIFEST.sha256.json` は自身を除くGit追跡ファイルのハッシュ一覧です。
チェックは追跡ファイルの一覧と作業ツリーの内容を照合します。
新しいファイルや削除を含む変更後は、公開対象だけをステージしてから更新してください。

```bash
git add <公開する追加・変更・削除のパス>
python tools/update_manifest.py --write
python tools/update_manifest.py --check
git add MANIFEST.sha256.json
```

ハッシュ一致は配布内容の同一性を確認するもので、実装の正しさの証明ではありません。
公開版を確定した後はコミットIDとタグを記録し、論文から対応する版を参照します。
