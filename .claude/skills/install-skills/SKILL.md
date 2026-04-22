---
name: install-skills
description: my-settings リポジトリにあるスキル・コマンド・エージェント・プラグインを、プロジェクトスコープまたはユーザースコープにインストールする。引数で `user` / `project` を指定してインストール先を切り替える。
allowed-tools: Bash(ls:*), Bash(find:*), Bash(cp:*), Bash(mkdir:*), Bash(cat:*), Read, Write, Edit
---

# install-skills スキル

`my-settings` リポジトリにあるスキル・コマンド・エージェント・プラグインを別プロジェクトまたはユーザーレベルにインストールする。

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
- `project`: カレントディレクトリのプロジェクトレベル (`./.claude/`)

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

**scope が未指定の場合**: ユーザーに `user` / `project` を確認する。

**type が未指定の場合**: 以下を確認して利用可能なアイテムを種別ごとに一覧表示し、ユーザーに選択してもらう。

```bash
# 利用可能アイテムの一覧取得
find "$SOURCE_DIR/skills"   -mindepth 1 -maxdepth 1 -type d 2>/dev/null | xargs -I{} basename {}
find "$SOURCE_DIR/commands" -name "*.md"  2>/dev/null | xargs -I{} basename {} .md
find "$SOURCE_DIR/agents"   -name "*.md"  2>/dev/null | xargs -I{} basename {} .md
find "$SOURCE_DIR/plugins"  -mindepth 1 -maxdepth 1 -type d 2>/dev/null | xargs -I{} basename {}
```

**name が未指定の場合**: 指定された type の一覧を表示してユーザーに選択してもらう。

### Step 3: インストール先パスの決定

| scope | 種別 | インストール先 |
|-------|------|---------------|
| `user` | skill | `~/.claude/skills/<name>/` |
| `user` | command | `~/.claude/commands/<name>.md` |
| `user` | agent | `~/.claude/agents/<name>.md` |
| `user` | plugin | `~/.claude/plugins/<name>/` |
| `project` | skill | `./.claude/skills/<name>/` |
| `project` | command | `./.claude/commands/<name>.md` |
| `project` | agent | `./.claude/agents/<name>.md` |
| `project` | plugin | `./.claude/plugins/<name>/` |

### Step 4: インストール実行

**skill / plugin の場合** (ディレクトリコピー):

```bash
DEST_DIR="<インストール先ディレクトリ>"
mkdir -p "$DEST_DIR"
cp -r "$SOURCE_DIR/<type>/<name>/." "$DEST_DIR/"
```

**command / agent の場合** (ファイルコピー):

```bash
DEST_DIR="<インストール先ディレクトリ>"
mkdir -p "$DEST_DIR"
cp "$SOURCE_DIR/<type>/<name>.md" "$DEST_DIR/<name>.md"
```

既にインストール先に同名のファイル/ディレクトリが存在する場合は、上書きして良いかユーザーに確認してから実行する。

### Step 5: プラグインの追加設定 (plugin のみ)

plugin をインストールした場合、`settings.json` の `enabledPlugins` にエントリを追加する必要がある。

対象の `settings.json` パスを決定する：
- `user` scope: `~/.claude/settings.json`
- `project` scope: `./.claude/settings.json`

`$SOURCE_DIR/plugins/<name>/.claude-plugin/plugin.json` を読み込み、`name` フィールドを取得してキー名にする。

```json
// settings.json の enabledPlugins に追記するイメージ
{
  "enabledPlugins": {
    "<plugin-name>@<marketplace-or-local>": true
  }
}
```

`settings.json` が存在しない場合は新規作成する。既存の場合は `enabledPlugins` キーに追記する（既存のエントリは消さない）。

> **注意**: `settings.json` の編集は Edit ツールを使い、既存の JSON 構造を壊さないよう慎重に行うこと。

### Step 6: 結果報告

インストール結果をユーザーに報告する：

```
✅ インストール完了

種別   : skill
名前   : record-demo
スコープ: user
インストール先: ~/.claude/skills/record-demo/
```

失敗した場合はエラー内容と対処方法を明示する。

## 注意事項

- `project` scope でインストールする場合のカレントディレクトリは、Claude が起動されたプロジェクトルートになる
- `~/.claude/skills/` にインストールしたスキルはすべてのプロジェクトで利用可能になる
- インストール後、スキルをすぐに使うには Claude Code を再起動する必要がある場合がある
- このスキル自体 (`install-skills`) を別プロジェクトにインストールする場合、インストール元は `.claude/skills/install-skills/` を使う
