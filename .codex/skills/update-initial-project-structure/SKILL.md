---
name: update-initial-project-structure
description: kmp-template-impl の実装を別プロジェクトの内容で更新し、InitialProjectStructure.json を impl に同期させる。「〇〇のコードを元に kmp-template-impl と kmp-template を更新して」「テンプレートの JSON を再生成して」と依頼されたときに使う。
---

# Update initial project structure

`InitialProjectStructure.json` は [kmp-template-impl](https://github.com/matsumo0922/kmp-template-impl) のスナップショットである。
実装の正本は impl にあり、JSON は impl から生成する。JSON を直接編集しない。

## 手順

### 1. impl を更新する

取り込み元プロジェクトの指定された revision を、識別子を impl のもの（`romaflow` / `RomaFlow`）へ置換して impl に反映する。
作業ツリーではなく `git archive <revision>` の内容を使い、未コミットの変更を混ぜない。

次のものは取り込み元に固有のため反映しない。

- `README.md` と `docs/`
- アプリ名、ランチャー名などの製品固有のリソース
- Firebase などの製品固有の設定値

置換後に取り込み元の識別子が残っていないことを grep で確認する。

### 2. impl を検証する

```sh
./gradlew detekt :androidApp:assembleDebug :shared:testAndroidHostTest :shared:compileKotlinIosSimulatorArm64
```

`local.properties` がない場合は `ANDROID_HOME` で SDK の場所を渡す。

### 3. JSON を更新する

```sh
python3 .codex/skills/update-initial-project-structure/scripts/update_initial_project_structure.py --since <commit>
```

`--since` には、JSON が最後に同期した impl の commit を渡す。
その commit 以降に impl へ追加されたファイルと、未追跡のファイルが新規に収録される。
省略時は `HEAD` であり、impl の未コミットの変更だけを反映する場合に使う。

| option | 既定値 | 内容 |
|---|---|---|
| `--impl` | `../kmp-template-impl` | impl の checkout |
| `--json` | `InitialProjectStructure.json` | 更新する JSON |
| `--since` | `HEAD` | 新規ファイルと統計値の差分の基準にする impl の commit |
| `--all` | 無効 | impl の全ファイルを収録対象にする |

script は収録済みの path を impl の作業ツリーと比較し、内容が変わったものを更新し、impl から消えたものを削除する。
収録対象外のファイルは `not included` として標準エラーに出力される。

### 4. 結果を確認する

- 出力された `updated` / `removed` / `added` が impl の変更と対応している
- 再実行すると3つとも 0 件になる
- `git diff --stat` の変更が `InitialProjectStructure.json` だけである

### 5. PR を作成する

impl と kmp-template のそれぞれで PR を作成し、impl を先にマージする。
JSON 内の binary の URL が `kmp-template-impl/HEAD` を参照するためである。

## JSON の値

- `content` 型の `hash` は内容の SHA-256、`size` は UTF-8 の byte 数
- `binary` 型は内容を持たず、`url` から取得する
- `tree` の値と `size.tokens` / `size.totalTokens` は文字数からの概算値であり、tokenizer の結果とは一致しない
- `size.totalTokens` / `size.characters` / `size.lines` は、収録対象外のファイルを含む impl 全体の値
