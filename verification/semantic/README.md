# 意味論・圏論論文の再現資料

対象: https://github.com/funashima/java_oop_pattern_learning_app
コミット: a92f4705f968d753952adaa7f5398e38c81d6a85
検証日: 2026-11-03 (Asia/Tokyo)
Python 3.12.14 / OpenJDK 17.0.20 / Linux x86_64

## 内容
- semantic_audit.py: 論文のA1-A8の境界検証。対象リポジトリを変更しない。
- audit_results/: 8件の記録と結果。変更した記録は実Java実行と区別して読むこと。
- baseline/: evaluate.py --liveによる26シナリオの記録、CSV、JSON。
- core_tests.txt: コア13件成功、GUI4件スキップのログ。
- cross_language/: Java・PythonそれぞれのAbstract Factory実装と、有限領域の比較結果。

## 実行
JDK 17以降の java をPATHへ追加する。対象コミットをチェックアウトした上で、

    python3 semantic_audit.py /path/to/java_oop_pattern_learning_app audit_output

を実行する。スクリプトは既存APIを読み込むため、この固定コミットを使用する。
Javaの変更例は一時ディレクトリで実行される。検証結果のPASSは、各ケースに指定した
期待結果が再現したことを表す。すべてのケースが教材契約PASSになるという意味ではない。

## ケース
A1: Strategyの入力0では正常/比較の全チェックポイントと最終結果が一致する。
A2: Discountへのcallを削除すると、状態整合性PASS・契約FAILとなる。
A3: Observerのログ上の引数だけ999加算しても、現行の両判定はPASSとなる。
A4: Observerを逆順通知しても、順序を要求しない現行契約ではPASSとなる。
A5: 参照教材のvalueのsetを消すと、状態整合性FAIL・契約PASSとなる。
A6: 直接観測のtotalだけ改変すると、状態整合性FAIL・契約PASSとなる。
A7: endを削除すると、状態整合性PASS・契約UNKNOWNとなる。
A8: return直後set前にチェックポイントを挿入すると2か所で整合性が失敗する。

この資料は8件の境界の再現を目的とし、未知誤りの検出率を評価するベンチマークではない。
測定された実行時間は環境依存であり、論文の性能優位の主張には使用していない。

## Abstract Factoryの独立した言語間比較

これは既存GUIに組み込んだ教材ではない。既存のJSON Linesイベント形式とも独立している。
追加依存ライブラリなしで、次のコマンドを実行できる。

    python3 cross_language/run_study.py --java /path/to/jdk/bin/java

JDK 17以降のjavaがPATHにあれば、--javaは省略できる。
実行はJavaソースファイルモードを使用する。出力先は--outputで変更できる。

- CodecStudy.java: JavaのEncoder、Decoder、CodecFactoryと5構成。
- codec_study.py: Pythonで独立に計算する同じ5構成。
- run_study.py: 実行、入力ごとの比較、集計、環境・ソースハッシュの保存。
- results/java.jsonl, python.jsonl: 全入力の実行結果。元の例外名も保持。
- results/summary.json, summary.csv: 比較結果と集計。

入力は0から255まで。10進表記と小文字・接頭辞なし・不要な先頭0なしの16進表記を使う。
各言語で5構成×256入力、合計2560回の往復処理を実行した。

| 構成 | 往復一致 | 値の不一致 | 解析例外 | 宣言系列と要求系列の一致 |
| --- | ---: | ---: | ---: | ---: |
| decimal | 256 | 0 | 0 | 256 |
| hex | 256 | 0 | 0 | 256 |
| mixed (Hex符号化、Decimal復号) | 10 | 90 | 156 | 0 |
| wrong_family (Hex指定、Decimalペア) | 256 | 0 | 0 | 0 |
| faulty_hex (復号値の最下位ビット反転) | 0 | 256 | 0 | 256 |

この表は各言語で同じ値となる。NumberFormatExceptionとValueErrorをParseErrorへ
正規化した1280組の入力別観測が全て一致した。集計値だけを比較しているわけではない。
宣言系列はプログラムのメタデータであり、型推論や振る舞いの証明の結果ではない。
言語間で一致することと契約を満たすことは別である。

さらに両言語で256入力のDecimalからHexへの再符号化を実行して照合した。
数値境界として(-1*8)/10の丸めと32ビット整数最大値への加算を確認した。
JavaのMapとPythonの辞書では、同じ内容の別実体の値比較が真、同一性比較が偽となる。
全ての結果はresults/に保存される。

有限の純粋計算に関する比較であり、任意文字列、生成時のヒープ、並行性、全言語の
翻訳、GUIの対応を証明するものではない。再現スクリプトのassertは、論文に記載した
期待結果と実行結果の照合であり、全コードの形式的証明ではない。
