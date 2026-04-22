---
name: record-demo
description: agent-browser で Web アプリの動作確認動画を自動録画するスキル。実装・デバッグ完了後に agent-browser で操作フローを確認し、そのまま録画まで完結させる。任意の Web アプリ（localhost / リモート）に対応。ログイン不要アプリにも対応。
allowed-tools: Bash(agent-browser:*), Bash(npx agent-browser:*), Bash(curl:*), Bash(ffmpeg:*), Bash(mkdir:*), Bash(node:*)
---

# record-demo スキル

## 概要

任意の Web アプリに対して `agent-browser` CLI で操作フローを確認し、そのまま動作確認動画を録画するスキル。

**操作フローは推測で書かない。必ず agent-browser で実際にアプリを操作して確認した内容をもとに録画を行うこと。**

探索（Phase 1）→ 録画（Phase 2）の 2 フェーズで完結する。Playwright は不要。

## トリガー条件

以下のいずれかで呼び出す：

- ユーザーが「録画して」「デモ動画を撮って」「record-demo」と言ったとき
- 実装・デバッグ完了後に動作確認動画が必要なとき（プロジェクトの CLAUDE.md にルールがある場合）

## 前提条件

- 対象アプリが起動済み（または起動できる状態）であること
- `agent-browser` がインストール済みであること
  ```bash
  npm install -g agent-browser && agent-browser install
  ```
- `ffmpeg` がインストール済みであること（動画レビュー用）
  ```bash
  brew install ffmpeg  # macOS
  ```

## 処理ステップ

### Step 1: 対象の特定

ユーザーへの質問または直前の実装内容から以下を確認する：

- **ベース URL**: `http://localhost:3000` など（ポート番号込みのフル URL）
- **アプリ名**: ファイル名に使う識別子（例: `my-app`）
- **デモで見せたい機能**: 実装した機能の概要
- **ログインの要否**: ログインが必要か、認証情報は何か

情報が不明な場合はユーザーに確認する。

### Step 2: サーバー疎通確認

```bash
curl -s -o /dev/null -w "%{http_code}" <BASE_URL>
```

200 系が返れば OK。失敗した場合はユーザーにサーバーの起動を依頼してスキルを中断する。

### Step 3: agent-browser で探索する（Phase 1）【必須】

> **⚠️ このステップをスキップして録画に進んではいけない。**
> URL・セレクタ・画面遷移の順序はすべて実際に操作して確認した値を使うこと。

**Agent tool のサブエージェントに委譲すること**（ブラウザ操作のグローバルルール参照）。

agent-browser CLI でアプリを実際に操作して以下を確認・記録する：

```bash
# 基本的な探索フロー
agent-browser open <BASE_URL>
agent-browser wait --load networkidle
agent-browser snapshot -i           # 要素 ref を取得（@e1, @e2 ...）
agent-browser screenshot            # 現在の画面を確認
```

**ログインフローの確認**（ログインが必要な場合）:

```bash
agent-browser open <BASE_URL>/login
agent-browser wait --load networkidle
agent-browser snapshot -i           # ログインフォームの ref を確認
# 例: @e1 [input] "Email", @e2 [input] "Password", @e3 [button] "Login"

agent-browser fill @e1 "user@example.com"
agent-browser fill @e2 "password"
agent-browser click @e3
agent-browser wait --url "**" --load networkidle  # ログイン後のリダイレクト待機
agent-browser get url               # ログイン後の URL を記録
```

**デモ操作フローの確認**:

```bash
agent-browser open <TARGET_PAGE_URL>
agent-browser wait --load networkidle
agent-browser snapshot -i           # 操作対象の ref を確認
agent-browser screenshot            # スクリーンショットで確認

# 対象ボタン・フォームを操作して画面遷移の順序を確認
agent-browser click @eN             # 操作したい要素をクリック
agent-browser wait --load networkidle
agent-browser get url               # 遷移後の URL を記録
agent-browser snapshot -i           # 遷移後の状態を確認

# スクロールが必要な場合（ページ全体を見せるデモなど）
agent-browser scroll 0 500          # Y 方向に 500px スクロール（量はページ高さに合わせる）
agent-browser wait 1000
```

**確認後に記録すること**:

- ログイン URL と各ページの実際の URL パス
- ログインフォームの ref と対応するラベル
- デモで操作するボタン・リンクの ref とテキスト
- 画面遷移の順序

### Step 4: 出力ディレクトリを準備する

```bash
mkdir -p .record/videos
```

タイムスタンプを生成する：

```bash
TS=$(date +%Y%m%d-%H%M%S)
```

### Step 5: agent-browser で録画する（Phase 2）

**Step 3 で起動した同一サブエージェント（`browser-agent`）に SendMessage で継続指示を送ること**（新規サブエージェントは起動しない）。
Step 3 で確認した ref・URL・操作順序をサブエージェントへの指示に含めること。Step 4 で生成した `TS` の値は文字列として SendMessage に埋め込む（シェル変数としてではなく、具体的な値 `20260422-143022` のように展開してから渡す）。

```bash
# 録画開始
agent-browser record start .record/videos/<APP_NAME>-${TS}.webm
agent-browser set viewport 1280 720

# ログイン（必要な場合）
agent-browser open <LOGIN_URL>
agent-browser wait --load networkidle
agent-browser snapshot -i                 # open 後は ref が変わるため再取得（Step 3 の ref をそのまま使わない）
agent-browser wait 500
agent-browser fill @e1 "<USERNAME>"       # snapshot -i で取得した ref を使う
agent-browser wait 300
agent-browser fill @e2 "<PASSWORD>"
agent-browser wait 300
agent-browser click @e3
agent-browser wait --load networkidle
agent-browser wait 800                    # ログイン完了を視覚的に見せる

# デモ操作（Step 3 で確認した内容をもとに生成）
agent-browser open <TARGET_URL>
agent-browser wait --load networkidle
agent-browser wait 1000                   # ページが映るように待機
agent-browser snapshot -i                 # 録画中に ref を再取得（ページ遷移後、またはSPA でDOM更新後は必須）
agent-browser click @eN
agent-browser wait 800
# ... 操作を続ける

# 録画終了
agent-browser record stop
agent-browser close
```

**録画時の注意**:

- 各操作の後に `agent-browser wait 500〜1000` を入れて操作が動画に映るようにする
- ページ遷移後は必ず `agent-browser snapshot -i` で ref を再取得する（古い ref は無効）
- 全体で 30〜90 秒程度の動画になるよう調整する

### Step 6: 動画をレビューして自己フィードバック

録画した動画を確認し、問題があれば修正する。

**フレーム抽出で動画を確認する**:

```bash
mkdir -p .record/review
ffmpeg -i .record/videos/<APP_NAME>-${TS}.webm -vf fps=1/5 .record/review/%03d.png -y
```

抽出した画像（`.record/review/001.png` 〜 `006.png` 等）を Read ツールで読み込んで以下を確認する：

- [ ] アプリが適切に表示されているか
- [ ] ログインが必要な場合、ログインできているか（ログイン画面のままになっていないか）
- [ ] 実装した機能が映っているか
- [ ] 動画全体を通して操作の流れが伝わるか
- [ ] エラーオーバーレイ・エラーダイアログが表示されていないか

**問題があった場合**: まずメインコンテキストで新しいタイムスタンプを生成し、その値を SendMessage に埋め込んでサブエージェントに撮り直しを指示する。

```bash
# メインコンテキストで実行してから SendMessage に値を埋め込む
TS_NEW=$(date +%Y%m%d-%H%M%S)
```

SendMessage に含めるコマンド（`${TS_NEW}` は上で生成した具体的な値に置換して渡す）:

```bash
agent-browser record stop    # 前回録画が残っている場合に備えたリセット（既に停止済みでも安全）
agent-browser close --all
agent-browser record start .record/videos/<APP_NAME>-${TS_NEW}.webm
# ... 再度ログイン〜デモ操作を繰り返す（open 後の snapshot -i も忘れずに）
agent-browser record stop
agent-browser close
```

撮り直し後は同じフレーム抽出手順（`ffmpeg` → Read で全フレームを確認）を再実施し、全項目 OK になったら Step 7 へ進む。
**問題がなければ**: Step 7 へ進む。

### Step 7: 結果報告

動画パスとレビュー結果をユーザーに報告する：

```
動作確認動画を録画しました: .record/videos/{app}-{timestamp}.webm

【動画レビュー】
- 起動・表示: OK
- ログイン: OK / スキップ（ログイン不要）
- 画面遷移: OK / NG（問題の説明）
- 実装機能の確認: OK
```

## 出力ファイル

| パス | 内容 |
|------|------|
| `.record/videos/{app}-{YYYYMMDD-HHmmss}.webm` | 録画動画（1280x720） |
| `.record/review/*.png` | フレーム抽出画像（レビュー後削除してよい） |

## サブエージェント運用ルール

グローバルルール（`~/.claude/CLAUDE.md`）に従い：

1. 探索・録画の試行錯誤は必ず Agent tool のサブエージェントに委譲する
2. サブエージェントには `name` を付与し（例: `browser-agent`）、Step 5（録画）・Step 6（撮り直し）いずれも同一サブエージェントに `SendMessage`（`to: "browser-agent"` 形式）で継続指示を送る。新規サブエージェントを起動しない
3. メインコンテキストには結果（成功/失敗、動画パス）だけ返させる

## 注意事項

- `.record/` ディレクトリはプロジェクトルートに自動作成される
- サーバーが起動していない場合はスキルを中断してユーザーに通知する
- ページ遷移後、および SPA で URL は変わらず DOM が更新されて新しい要素が追加された後も、必ず `agent-browser snapshot -i` で ref を再取得すること（古い ref は無効）
- `.record/` を `.gitignore` に追加することを推奨する

## よくあるトラブル

| 症状 | 対処 |
|------|------|
| `agent-browser` が見つからない | `npm install -g agent-browser && agent-browser install` |
| ログイン後もログイン画面のまま | `wait --load networkidle` の前後に `wait 1000` を追加、または `wait --url` で条件指定 |
| ref が見つからない（`@eN not found`） | ページ遷移後に `snapshot -i` を再実行して新しい ref を取得する |
| 動画が録画されない | `agent-browser record stop` が実行されたか確認、`agent-browser close --all` で状態リセット |
| `ffmpeg` が見つからない | `brew install ffmpeg` |
