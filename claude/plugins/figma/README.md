# Figma to React プラグイン

FigmaデザインからReactコンポーネントを自動実装するためのClaude Codeプラグインです。

## 概要

このプラグインは、Figma MCPを利用してFigmaのデザイン情報を取得し、View-Service分離パターンに従ったReactコンポーネントを自動生成します。

## 機能

- Figma MCPを使用したデザイン情報の取得
- View-Service分離パターンに従ったコンポーネント生成
- CSS Modulesによるスタイリング
- TypeScriptによる型安全な実装
- Storybookストーリーの自動生成

## インストール方法

### 方法1: マーケットプレイス経由（推奨）

1. **マーケットプレイスを追加**

```shell
/plugin marketplace add owner/mep-ai-plugins
```

2. **プラグインをインストール**

```shell
/plugin install figma@mep-plugins
```

3. **Figma MCPの設定**（次のセクションを参照）

### 方法2: 直接コピー（開発用）

このディレクトリの内容をプロジェクトの`.claude`ディレクトリにコピーします：

```bash
# プロジェクトルートで実行
cp -r /path/to/mep-ai-plugins/claude-code/figma/{commands,agents,skills} .claude/
```

## Figma MCPの設定

Claude Code設定ファイル（`~/.claude/config.json`）にFigma MCPサーバーの設定を追加します：

```json
{
  "mcpServers": {
    "figma": {
      "command": "npx",
      "args": [
        "-y",
        "@figma/mcp-server-figma"
      ],
      "env": {
        "FIGMA_PERSONAL_ACCESS_TOKEN": "your-figma-token-here"
      }
    }
  }
}
```

Figma Personal Access Tokenの取得方法：
1. Figmaにログイン
2. Settings → Account → Personal Access Tokens
3. 新しいトークンを生成

## 使用方法

### コマンド: `/figma`

FigmaデザインからReactコンポーネントを実装します。

```bash
/figma <figma-url> <component-path>
```

#### 引数

- `figma-url`: FigmaデザインのURL（node-idを含む）
  - 例: `https://figma.com/design/abc123/Design?node-id=10-20`
- `component-path`: 実装先のコンポーネントパス
  - 例: `apps/customer/src/components/molecules/UserCard`

#### 使用例

```bash
# カスタマーアプリにコンポーネントを実装
/figma https://figma.com/design/abc123/Design?node-id=10-20 apps/customer/src/components/molecules/UserProfileCard

# 共通UIパッケージにatomsを実装
/figma https://figma.com/design/abc123/Design?node-id=5-10 packages/ui/src/atoms/StatusBadge
```

## 生成されるファイル

コマンドを実行すると、以下のファイルが生成されます：

```
<component-path>/
├── index.tsx              # エントリーポイント
├── view.tsx              # UIコンポーネント（Pure UI）
├── service.ts            # ビジネスロジック・hooks（モック実装）
├── style.module.scss     # CSS Modules
└── test/
    └── stories.tsx       # Storybookストーリー
```

### 各ファイルの役割

#### index.tsx
- serviceとviewを組み合わせてコンポーネント化
- 外部に公開するインターフェース

#### view.tsx
- 純粋なUIコンポーネント
- propsで受け取ったデータを表示
- ビジネスロジックを含まない

#### service.ts
- カスタムフックとして実装
- 状態管理とイベントハンドラ
- **初期はモック実装**（型定義のみ正確）

#### style.module.scss
- CSS Modulesでスタイル定義
- プロジェクトのCSS変数を使用

#### test/stories.tsx
- Storybookストーリー
- コンポーネントの動作確認用

## プラグインの構成

### コマンド

- `commands/figma.md`: Figma to Reactコマンド定義

### エージェント

- `agents/figma-impl.md`: Figma UI実装エージェント

### スキル

- `skills/ui-impl/SKILL.md`: UI実装スキル

### プラグインマニフェスト

- `.claude-plugin/plugin.json`: プラグインのメタデータと設定

## 実装パターン

このプラグインは以下のパターンに従います：

### View-Service分離

- **View**: 純粋なUI表示
- **Service**: ビジネスロジック（初期はモック）
- **Index**: ViewとServiceの組み合わせ

### CSS設計

- CSS Modulesを使用
- プロジェクト定義のCSS変数を利用
- フラットなクラス構造

### 型安全性

- すべてのpropsに型定義
- `UseService`型のエクスポート
- `any`型を使用しない

## 重要な注意事項

### モック実装について

生成される`service.ts`は**モック実装**です：

- ✅ 型定義は正確に実装
- ✅ UIの動作確認が可能
- ❌ 実際のAPIアクセスは未実装
- ❌ 複雑なビジネスロジックは未実装

実際のビジネスロジックは、UI実装確認後に別途追加してください。

### Atomic Design

コンポーネントの階層を意識してください：

- **atoms**: 単一の基本要素（Button, Input, Icon）
- **molecules**: 複数のatomsの組み合わせ（SearchBar, UserAvatar）
- **organisms**: 複数のmoleculesの組み合わせ（Header, Card）

### CSS変数の使用

プロジェクト定義のCSS変数を使用してください：

```scss
color: var(--color-gray-text);
background: var(--color-primary);
border-color: var(--color-gray-border);
```

## トラブルシューティング

### Figma MCP接続エラー

1. Personal Access Tokenが正しく設定されているか確認
2. トークンの有効期限を確認
3. Claude Codeを再起動

### コンポーネント生成エラー

1. Figma URLにnode-idが含まれているか確認
2. 実装先パスが正しいか確認
3. 既存ファイルとの衝突がないか確認

## 次のステップ

実装後の確認：

1. **Storybookで確認**: `pnpm storybook`
2. **型チェック**: `pnpm type:check`
3. **Lint**: `pnpm lint`
4. **ビジネスロジック実装**: `service.ts`を実装

## サポート

問題や提案がある場合は、リポジトリのIssueを作成してください。
