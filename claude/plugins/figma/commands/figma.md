# Figma UI実装コマンド `/figma <figma-url> <component-path>`

FigmaデザインからReactコンポーネントを自動実装します。

## 使用方法

```
/figma <figma-url> <component-path>
```

### 引数

- **figma-url**: FigmaデザインのURL（node-idを含む完全なURL）
  - 例: `https://figma.com/design/FILE_KEY/FILE_NAME?node-id=1-2`
- **component-path**: 実装先のコンポーネントパス
  - 例: `apps/customer/src/components/molecules/UserCard`
  - 例: `packages/ui/src/atoms/Badge`

### 使用例

```bash
# カスタマーアプリのmoleculesに実装
/figma https://figma.com/design/abc123/Design?node-id=10-20 apps/customer/src/components/molecules/UserProfileCard

# UIパッケージのatomsに実装
/figma https://figma.com/design/abc123/Design?node-id=5-10 packages/ui/src/atoms/StatusBadge

# サプライヤーアプリのorganismsに実装
/figma https://figma.com/design/abc123/Design?node-id=30-40 apps/supplier/src/components/organisms/OrderList
```

## 実行内容

**figma-implエージェント**を起動し、以下のフローで実装を行います：

1. Figma URLからnode-idを抽出
2. Figma MCP `get_design_context`でデザイン情報を取得
3. 必要に応じて`get_variable_defs`で変数定義を取得
4. `ui-impl`スキルを使用してコンポーネント実装
5. View-Service分離パターンに従った実装
6. CSS Modulesによるスタイリング
7. Storybookストーリーの作成

## 実装されるファイル

指定されたコンポーネントパスに以下のファイルが作成されます：

```
<component-path>/
├── index.tsx              # エントリーポイント
├── view.tsx              # UIコンポーネント
├── service.ts            # ビジネスロジック・hooks
├── style.module.scss     # スタイル
└── test/
    └── stories.tsx       # Storybookストーリー
```

---

{{
## 実行手順

### 1. 引数の検証

- Figma URLの形式を検証（node-idが含まれているか確認）
- コンポーネントパスの形式を検証（有効なパスか確認）

### 2. figma-implエージェントの起動

Task toolを使用してfigma-implエージェントを起動：

```typescript
Task({
  subagent_type: "figma-impl",
  description: "FigmaからUI実装",
  prompt: `以下のFigmaデザインからコンポーネントを実装してください：

  Figma URL: ${figma_url}
  実装先パス: ${component_path}

  1. Figma MCPでデザイン情報を取得
  2. ui-implスキルを使用して実装
  3. View-Service分離パターンに従う
  4. CSS Modulesでスタイリング
  5. Storybookストーリーを作成`
})
```

### 3. 結果の確認

エージェントが返した結果をユーザーに報告：

- 作成されたファイルのリスト
- 実装の概要
- 次のアクション（テスト実行、Storybook確認など）

## 重要な注意事項

1. **Figma MCP利用**: 必ずFigma MCPを通してデザイン情報を取得
2. **View-Service分離**: index.tsx, view.tsx, service.tsの役割を明確に分離
3. **CSS Modules**: style.module.scssを使用し、必ず`@use 'styles/utils/' as *;`を先頭に記述
4. **型安全性**: すべてのpropsとstateに適切な型定義を付与
5. **Atomic Design**: コンポーネントの階層（atoms/molecules/organisms）を意識

}}
