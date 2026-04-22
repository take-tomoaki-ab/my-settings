---
name: ui-impl
description: Figmaデザイン情報からReactコンポーネントを実装。View-Service分離、CSS Modules、Storybookを含む完全な実装を生成。
context: fork
allowed-tools: Read, Write, Edit, Grep, Glob
args:
  - name: component_path
    description: 実装先のコンポーネントパス
    required: true
  - name: design_info
    description: Figma MCPから取得したデザイン情報（JSON形式）
    required: true
---

# UI実装スキル

Figmaから取得したデザイン情報を基に、プロジェクト規約に従ったReactコンポーネントを実装します。

## 実装原則

### 1. View-Service分離パターン

MEP-Frontendプロジェクトの基本パターンに従います：

```
ComponentName/
├── index.tsx              # コンポジション層（他ファイルをまとめてexport）
├── view.tsx              # Pure UIコンポーネント（表示のみ）
├── service.ts            # ビジネスロジック、hooks、状態管理
├── style.module.scss     # CSS Modules
└── test/
    └── stories.tsx       # Storybookストーリー
```

#### index.tsx の役割
- serviceとviewをインポートしてコンポーネント化
- 外部に公開するインターフェースを定義

#### view.tsx の役割
- 純粋なUIコンポーネント
- propsとして受け取ったデータを表示
- イベントハンドラはpropsとして受け取る
- ビジネスロジックを含まない

#### service.ts の役割
- カスタムフックとして実装
- 状態管理（useState, useAtom等）
- API呼び出し
- イベントハンドラの定義
- 計算ロジック

### 2. CSS Modules規約

```scss
// 必ずファイル先頭で相対パスでutilsをインポート
@use '../../styles/utils/' as *;
// または
@use '../../../styles/utils/' as *;

// クラスはフラットに定義（ネストを避ける）
.root {
  display: flex;
  gap: 8px;
}

.item {
  color: var(--color-gray-text);
}

// hover等の疑似クラスは&を使用
.button {
  background: var(--color-primary);

  &:hover:not(:disabled) {
    background: var(--color-primary-hover);
  }
}
```

### 3. 色の使用

プロジェクト定義済みのCSS変数を使用：

```scss
// テキスト色
color: var(--color-gray-text);
color: var(--color-gray-textContrast);

// 背景色
background: var(--color-primary);
background: var(--color-gray-bg);

// ボーダー
border-color: var(--color-gray-border);
```

### 4. 高さ表現（z-index / box-shadow）

#### z-indexレベル
- 0: デフォルト
- 1: Dropdown, DatePicker, Popover, Tooltip
- 2: Drawer
- 3: グローバルヘッダー, Toast
- 4: Dialog

#### box-shadowの使用
高さの表現にのみ使用し、境界線やコントラストをつける目的で使用しない

### 5. TypeScript型定義

```typescript
// view.tsx
export type Props = {
  title: string
  description?: string
}

export const view = (useService: UseService) => {
  const ComponentName: FC<Props> = ({ title, description }) => {
    const { state, handleSubmit } = useService()

    // ...

    return (
      <>
      // ...
      </>
    )
  }
}

// service.ts
export const useService = () => {
  const [state, setState] = useState<StateType>(initialState)

  const handleSubmit = () => {
    // logic
  }

  return {
    state,
    handleSubmit,
  }
}

export type UseService = typeof useService

// index.tsx
import { useService } from './service'
import { view } from './view'

export default view(useService)
```

### 6. serviceのモック実装

**重要**: UI実装時、service.tsの中身はモック実装で構いません。

#### モック実装の原則

1. **型定義は正確に行う**
   - 返り値の型を適切に定義
   - propsやstateの型を明確にする
   - `export type UseService = typeof useService` で型をエクスポート

2. **返り値は適当なモック値でOK**
   - 文字列: `"Sample Text"`, `"Mock Value"`
   - 数値: `0`, `100`, `42`
   - 真偽値: `false`, `true`
   - 配列: `[]`, `[{ id: 1, name: "Sample" }]`
   - 関数: `() => {}`, `() => console.log('mock')`

3. **状態管理は最低限**
   - useState は必要最低限のみ
   - 複雑なロジックは不要
   - UIの動作確認ができる程度でOK

#### モック実装例

```typescript
// service.ts - モック実装
import { useState } from 'react'

export const useService = () => {
  // 最低限の状態管理
  const [isExpanded, setIsExpanded] = useState(false)

  // モックのイベントハンドラ（実装は空でOK）
  const handleClick = () => {
    setIsExpanded(!isExpanded)
  }

  const handleEdit = () => {
    console.log('Edit clicked - mock implementation')
  }

  const handleDelete = () => {
    console.log('Delete clicked - mock implementation')
  }

  // モックデータを返す
  return {
    // モック状態
    isExpanded,
    isLoading: false,
    error: null,

    // モックデータ
    userName: "山田太郎",
    email: "yamada@example.com",
    avatarUrl: "https://via.placeholder.com/150",
    joinedAt: "2024-01-01",

    // イベントハンドラ
    handleClick,
    handleEdit,
    handleDelete,
  }
}

export type UseService = typeof useUserCardService
```

#### 実際の実装は後から

ビジネスロジックの実装は、UI実装完了後に別途行います：

- API呼び出し
- データ変換ロジック
- バリデーション
- エラーハンドリング
- 複雑な状態管理

**現時点では**：
- ✅ 型定義を正確に
- ✅ UIが動作するモック値
- ❌ 実際のAPIアクセスは不要
- ❌ 複雑なビジネスロジックは不要

## 実装手順

### ステップ1: デザイン情報の解析

受け取ったFigmaデザイン情報から以下を抽出：

1. **構造**
   - 要素の階層関係
   - レイアウト（flex, grid）
   - 要素のサイズ

2. **スタイル**
   - 色（テキスト、背景、ボーダー）
   - タイポグラフィ（フォントサイズ、太さ）
   - スペーシング（margin, padding, gap）
   - 角丸、シャドウ

3. **インタラクティブ要素**
   - ボタン
   - 入力フィールド
   - クリック可能な要素
   - 状態（hover, active, disabled）

### ステップ2: コンポーネントの設計

1. **Props設計**
   - 必須のprops
   - オプショナルのprops
   - イベントハンドラのprops
   - 適切な型定義

2. **状態管理の検討（モック実装で十分）**
   - ローカル状態が必要か → 最低限のuseStateでモック
   - Jotai atomが必要か → UI実装時は不要、型定義のみ
   - フォーム状態管理が必要か → UI実装時は不要、型定義のみ
   - **注意**: 実際のビジネスロジックは後から実装

3. **階層の決定**
   - atoms/molecules/organismsのどれか
   - どのapp/packageに配置するか

### ステップ3: ファイル作成

#### 3-1. style.module.scss の作成

```scss
@use '../../styles/utils/' as *;

.root {
  // Figmaのレイアウト情報から
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header {
  // Figmaのスタイル情報から
  color: var(--color-gray-text);
  font-size: 18px;
  font-weight: 600;
}

.content {
  // ...
}
```

#### 3-2. view.tsx の作成

```typescript
import { type UseService } from './service'
import s from './style.module.scss'

export type Props = {
  // Figmaから抽出したprops
  title: string
  description?: string
}

export const view = (useService: UseService) => {
  const ComponentName: FC<Props> = ({ title, description }) => {
    const { isLoading, handleClick } = useService()
    return (
      <div className={s.root}>
        <h2 className={s.header}>{title}</h2>
        {description && <p className={s.content}>{description}</p>}
        <button onClick={handleClick} className={s.button}>
          Submit
        </button>
      </div>
    )
  }
}
```

#### 3-3. service.ts の作成（モック実装）

**注意**: service.tsは型定義を正確に行い、返り値はモック値でOKです。

```typescript
import { useState } from 'react'

export const useService = () => {
  // 最低限の状態管理（モック）
  const [isLoading, setIsLoading] = useState(false)

  // イベントハンドラ（モック実装）
  const handleClick = () => {
    // 実際のビジネスロジックは後から実装
    console.log('Click handler - mock implementation')
    setIsLoading(!isLoading)
  }

  // モックデータと状態を返す
  return {
    isLoading,
    handleClick,
    // 必要に応じて他のモックデータも追加
    // userName: "サンプルユーザー",
    // items: [],
  }
}

// 型定義は必ずエクスポート
export type UseService = typeof useService
```

#### 3-4. index.tsx の作成

```typescript
import { useService } from './service'
import { view } from './view'

export default view(useService)
```

#### 3-5. test/stories.tsx の作成

```typescript
import type { Meta, StoryObj } from '@storybook/react'
import { ComponentName } from '../index'

const meta = {
  title: 'Components/Molecules/ComponentName',
  component: ComponentName,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof ComponentName>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    title: 'Sample Title',
    description: 'Sample description text',
  },
}

export const WithoutDescription: Story = {
  args: {
    title: 'Sample Title',
  },
}
```

### ステップ4: 実装の検証

1. **TypeScript型チェック**
   - すべてのpropsに型定義があるか
   - any型を使用していないか

2. **スタイル規約チェック**
   - `@use 'styles/utils/' as *;` があるか
   - CSS変数を使用しているか
   - クラス名がフラットか

3. **View-Service分離チェック**
   - viewにビジネスロジックがないか
   - serviceに表示ロジックがないか
   - index.tsxでコンポジションされているか

## Figmaデザイン情報のマッピング

### レイアウト

- **Auto Layout** → `display: flex`, `gap`
- **Padding** → `padding`
- **Spacing** → `gap`, `margin`

### スタイル

- **Fill Color** → `background-color`, `color`
- **Stroke** → `border`
- **Corner Radius** → `border-radius`
- **Effect (Shadow)** → `box-shadow`

### テキスト

- **Font Size** → `font-size`
- **Font Weight** → `font-weight`
- **Line Height** → `line-height`
- **Letter Spacing** → `letter-spacing`

## エラーハンドリング

1. **パス不正**: 指定されたパスが存在しない場合はディレクトリを作成
2. **ファイル存在**: 既存ファイルがある場合は上書き確認
3. **デザイン情報不足**: 必要な情報が不足している場合は適切なデフォルト値を使用
4. **型定義エラー**: TypeScriptの型エラーが出ないように適切に型を定義

## 使用例

```bash
# moleculesレベルのコンポーネント実装
/ui-impl apps/customer/src/components/molecules/UserCard ${design_info}

# atomsレベルのコンポーネント実装
/ui-impl packages/ui/src/atoms/Badge ${design_info}

# organismsレベルのコンポーネント実装
/ui-impl apps/supplier/src/components/organisms/OrderTable ${design_info}
```
