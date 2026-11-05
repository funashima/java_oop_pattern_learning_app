# 論文の再現資料

実行手順と対象版は [docs/REPRODUCIBILITY.md](../docs/REPRODUCIBILITY.md) を参照してください。

`semantic/` は、配布済み `semantic_verification.zip` の内容をバイト単位で保持したものです。
スクリプト・元のREADME・実行記録を変更せずに収録しています。

- `semantic/semantic_audit.py` と `semantic/audit_results/`：基準コミット `a92f470` に対するA1〜A8。
- `semantic/baseline/` と `semantic/core_tests.txt`：同じ基準版の再検証。
- `semantic/cross_language/`：GUIとは独立したJava/Python実装と入力別の比較結果。

`semantic/README.md` の「現行」は、資料作成時の固定基準版を指します。
独立Codec実験を「GUIに組み込んだ教材ではない」とする説明は、独立Python実装がGUIの実行系ではないという意味です。
5教材版GUIのAbstract Factory教材は、Javaを実行してPythonで再生・判定する別の検証対象です。

保存結果を読むことと再実行することを区別し、再実行時は必ず別の出力先を指定してください。
元スクリプトには結果フォルダを既定の出力先とするものがあります。
