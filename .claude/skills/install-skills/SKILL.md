---
name: install-skills
description: カレントディレクトリの `claude/` にあるスキル・コマンド・エージェント・プラグインを、ユーザースコープ（~/.claude/）またはプロジェクトスコープ（指定パスの .claude/）にインストールする。引数で `user` / `project` を指定してインストール先を切り替える。
allowed-tools: Bash(ls:*), Bash(find:*), Bash(cp:*), Bash(mkdir:*), Bash(cat:*), Read, Write, Edit
---

# install-skills スキル

カレントディレクトリの `claude/` にあるスキル・コマンド・エージェント・プラグインを、ユーザーレベルまたは指定プロジェクトにインストールする。

## 呼び出し形式

```
/install-skills [scope] [type] [name]
```

| 引数 | 値 | 省略時 |
|------|----|--------|
| `scope` | `user` または `project` | 確認する |
| `type` | `skill` / `command` / `agent` / `plugin` | 一覧を表示して選択 |
| `name` | インストールするアイテム名 | 一覧を表示して選択 |

- `user`: ユーザーレベル (`~/.claude/`)
- `project`: 指定したプロジェクトのプロジェクトレベル（パスはユーザーに確認する）

## インストール元

スキル実行時のカレントディレクトリ（= このスキルを呼び出したリポジトリのルート）の `claude/` ディレクトリを使う。

```bash
SOURCE_DIR="$(pwd)/claude"
```

| type | インストール元パス |
|------|------------------|
| `skill` | `$SOURCE_DIR/skills/<name>/` |
| `command` | `$SOURCE_DIR/commands/<name>.md` |
| `agent` | `$SOURCE_DIR/agents/<name>.md` |
| `plugin` | `$SOURCE_DIR/plugins/<name>/` |

## 処理ステップ

### Step 1: インストール元パスの特定

```bash
SOURCE_DIR="$(pwd)/claude"
```

`$SOURCE_DIR` ディレクトリが存在するか確認する。存在しない場合は「カレントディレクトリに `claude/` ディレクトリが見つかりません。このスキルは `claude/` ディレクトリを持つリポジトリ内で実行してください」と伝えてスキルを終了する。

### Step 2: 引数の解決

**scope が未指定の場合**: 以下のフォーマットでユーザーに確認する。

```
インストール先を選択してください。

  user    : すべてのプロジェクトで利用可能 (~/.claude/)
  project : 特定のプロジェクトのみで利用可能 (<PROJECT_PATH>/.claude/)

user / project を入力してください:
```

`project` を選んだ場合は、**次のステップ（type 選択）に進む前に**インストール先プロジェクトの絶対パスを確認する:

```
インストール先プロジェクトの絶対パスを入力してください（例: /path/to/my-project）:
```

`scope` が引数で `project` と指定されていた場合も同様に、まずプロジェクトパスをユーザーに確認してから type 選択に進む。

**type が未指定の場合**: 以下を確認して利用可能なアイテムを種別ごとに一覧表示し、ユーザーに type を選択してもらう。**候補が 0 件の種別は表示しない。**

```bash
# 利用可能アイテムの一覧取得（アルファベット順にソート）
find "$SOURCE_DIR/skills"   -mindepth 1 -maxdepth 1 -type d 2>/dev/null | xargs -I{} basename {} | sort
find "$SOURCE_DIR/commands" -name "*.md"  2>/dev/null | xargs -I{} basename {} .md | sort
find "$SOURCE_DIR/agents"   -name "*.md"  2>/dev/null | xargs -I{} basename {} .md | sort
find "$SOURCE_DIR/plugins"  -mindepth 1 -maxdepth 1 -type d 2>/dev/null | xargs -I{} basename {} | sort
```

表示フォーマット（種別を見出しにして配下にアイテムを箇条書き）:

```
インストールする種別を選択してください。

skill:
  - record-demo
  - empirical-prompt-tuning

plugin:
  - figma

種別を入力してください (skill / plugin):
```

**name が未指定の場合**: type 選択後、**ユーザーが type を入力するまで待ってから**次の返答でその種別のアイテム一覧を表示し、name を選択してもらう。scope・type・name の3項目を同一返答内でまとめて聞かないこと（必ず1問1答で進める）。

```
インストールする skill を選択してください。

  - record-demo
  - empirical-prompt-tuning

名前を入力してください:
```

### Step 3: インストール先パスの決定

| scope | 種別 | インストール先 |
|-------|------|---------------|
| `user` | skill | `~/.claude/skills/<name>/` |
| `user` | command | `~/.claude/commands/<name>.md` |
| `user` | agent | `~/.claude/agents/<name>.md` |
| `user` | plugin | `~/.claude/plugins/<name>/` |
| `project` | skill | `<PROJECT_PATH>/.claude/skills/<name>/` |
| `project` | command | `<PROJECT_PATH>/.claude/commands/<name>.md` |
| `project` | agent | `<PROJECT_PATH>/.claude/agents/<name>.md` |
| `project` | plugin | `<PROJECT_PATH>/.claude/plugins/<name>/` |

`project` scope での `<PROJECT_PATH>` は Step 2 でユーザーに確認した絶対パスを使う。

### Step 4: インストール実行

プレースホルダーの置換ルール:

| プレースホルダー | 置換値 |
|-----------------|--------|
| `<type>` | `skills` / `commands` / `agents` / `plugins`（type の複数形ディレクトリ名） |
| `<name>` | ユーザーが指定したアイテム名 |
| `<インストール先ディレクトリ>` | Step 3 テーブルで決定した **フルパス**（例: `/Users/s28773/.claude/skills/record-demo`） |

**skill / plugin の場合** (ディレクトリコピー):

```bash
# 例: user scope, skill, record-demo
DEST_DIR="$HOME/.claude/skills/record-demo"
mkdir -p "$DEST_DIR"
cp -r "$SOURCE_DIR/skills/record-demo/." "$DEST_DIR/"
```

**command / agent の場合** (ファイルコピー):

```bash
# 例: user scope, command, look-back
DEST_DIR="$HOME/.claude/commands"
mkdir -p "$DEST_DIR"
cp "$SOURCE_DIR/commands/look-back.md" "$DEST_DIR/look-back.md"
```

コピー前に既存ファイル/ディレクトリの有無を確認する:

```bash
# skill / plugin の場合
test -d "$DEST_DIR" && echo "exists"

# command / agent の場合
test -f "$DEST_DIR/<name>.md" && echo "exists"
```

既に存在する場合は「`<name>` は既にインストール済みです。上書きしますか？ (y/N):」と確認してから実行する。N を選んだ場合は「インストールをキャンセルしました。」と伝えてスキルを終了する。

### Step 5: プラグインの追加設定 (plugin のみ)

plugin をインストールした場合、`settings.json` の `enabledPlugins` にエントリを追加する必要がある。

対象の `settings.json` パスを決定する：
- `user` scope: `~/.claude/settings.json`
- `project` scope: `<PROJECT_PATH>/.claude/settings.json`（Step 2 で確認したインストール先プロジェクトのパス）

`$SOURCE_DIR/plugins/<name>/.claude-plugin/plugin.json` を読み込み、`name` フィールドと `marketplace` フィールドを取得する。

`enabledPlugins` のキー形式: `"<plugin-name>@<marketplace>"`

- `plugin.json` に `marketplace` フィールドがある場合: `"<name>@<marketplace>"` を使う
- `plugin.json` に `marketplace` フィールドがない場合（ローカルプラグイン）: `"<name>@local"` を使う

```json
// settings.json の enabledPlugins に追記するイメージ（figma の場合）
{
  "enabledPlugins": {
    "figma@local": true
  }
}
```

`settings.json` が存在しない場合は新規作成する。既存の場合は `enabledPlugins` キーに追記する（既存のエントリは消さない）。

> **注意**: `settings.json` が既に存在する場合は Edit ツールで追記し、既存の JSON 構造を壊さないよう慎重に行うこと。ファイルが存在しない場合は Write ツールで新規作成する。

### Step 6: 結果報告

インストール結果をユーザーに報告する：

**skill / command / agent の場合**:

```
✅ インストール完了

種別      : skill
名前      : record-demo
スコープ  : user
インストール先: ~/.claude/skills/record-demo/
```

**plugin の場合**（settings.json 更新も含めて報告する）:

```
✅ インストール完了

種別      : plugin
名前      : figma
スコープ  : project
インストール先: /path/to/my-project/.claude/plugins/figma/

settings.json 更新済み:
  /path/to/my-project/.claude/settings.json
  enabledPlugins に "figma@mep-plugins" を追記しました。
```

失敗した場合はエラー内容と対処方法を明示する。

## 注意事項

- `project` scope でインストールする場合のカレントディレクトリは、Claude が起動されたプロジェクトルートになる
- `~/.claude/skills/` にインストールしたスキルはすべてのプロジェクトで利用可能になる
- インストール後、スキルをすぐに使うには Claude Code を再起動する必要がある場合がある
- このスキル自体 (`install-skills`) を別プロジェクトにインストールする場合、インストール元は `.claude/skills/install-skills/` を使う
