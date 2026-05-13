# PRレビューコメントを確認して対応・返信する
`/review-respond [pr-url|reviewer-name] [comment-url?]`

PRについたレビューコメントを確認し、コード修正または返信で対応する。

## 引数

- **第1引数** (オプション)
  - PR URL (`https://github.com/org/repo/pull/123`): そのPRのレビューを確認
  - レビュアー名 (`@username` または `username`): そのレビュアーのコメントに絞り込み
  - 省略時: 現在ブランチのPRを `gh pr view` で自動検出
- **第2引数** (オプション)
  - レビューコメントURL (`https://github.com/.../pull/123#discussion_r456` 形式): そのスレッドのみ対象
  - 第1引数がレビュアー名でも組み合わせ可能

## 使用例

```bash
# 現在ブランチのPRを自動検出して全コメントを確認
/review-respond

# 特定PRのコメントを確認
/review-respond https://github.com/org/repo/pull/123

# レビュアー名で絞り込み
/review-respond john-doe

# 特定のコメントスレッドのみ対応
/review-respond https://github.com/org/repo/pull/123#discussion_r456789

# レビュアー名 + コメントURLの組み合わせ
/review-respond john-doe https://github.com/org/repo/pull/123#discussion_r456789
```

## 動作概要

1. PR・コメントを特定（gh CLI）
2. レビューコメントを取得して整理表示
3. 各コメントの対応方針をユーザーに提示・確認
4. コード修正 or 返信コメントで対応
5. 完了報告

---

{{

## 実行手順

`review-respond` スキルを読み込んで実行する。

### Step 1: PR・コメントを特定する

引数 `$ARGUMENTS` を解析して対象PRを特定する:

| パターン | 解釈 |
|---------|------|
| `https://github.com/.../pull/NNN` | そのPRを対象にする |
| `https://github.com/.../pull/NNN#discussion_rXXX` または `.../pulls/comments/XXX` | そのコメントスレッドのみ対象 |
| `@username` / `username` (URL以外の文字列) | レビュアー名でフィルタ |
| 引数なし | 現在ブランチのPRを自動検出 |

```bash
# PR URL が与えられた場合
gh pr view <pr-url> --json number,url,baseRepository,headRepository \
  --jq '{number: .number, repo: .headRepository.nameWithOwner}'

# 引数なし（現在ブランチ）
gh pr view --json number,url,baseRepository,headRepository \
  --jq '{number: .number, repo: .headRepository.nameWithOwner}'
```

コメントURLが指定された場合は URL から owner/repo・PR番号・comment ID を全て抽出できるため `gh pr view` は不要。
- `#discussion_r(\d+)` → comment ID（PR番号もURLに含まれる）
- `/pulls/comments/(\d+)` → comment ID（PR番号がURLにない場合はコメント取得後に `pull_request_url` から抽出）

### Step 2: レビュー情報を取得する

```bash
# レビュー一覧（APPROVED / CHANGES_REQUESTED / COMMENTED）
gh api repos/<owner>/<repo>/pulls/<number>/reviews \
  --jq '[.[] | {id, reviewer: .user.login, state, body, url: .html_url, submitted_at}]'

# インラインコメント一覧
gh api repos/<owner>/<repo>/pulls/<number>/comments \
  --jq '[.[] | {
    id,
    reviewer: .user.login,
    path,
    line,
    body,
    diff_hunk,
    url: .html_url,
    in_reply_to_id,
    review_id: .pull_request_review_id,
    created_at
  }]'
```

コメントURL指定時は代わりに以下を実行（reviews API はスキップ可）:

```bash
# 対象コメントを取得
gh api repos/<owner>/<repo>/pulls/comments/<comment-id> \
  --jq '{id, reviewer: .user.login, path, line, body, url: .html_url, in_reply_to_id}'

# スレッド全体（root + 返信）を取得
gh api repos/<owner>/<repo>/pulls/<number>/comments \
  --jq '[.[] | select(.id == <comment-id> or .in_reply_to_id == <comment-id>) | {id, reviewer: .user.login, body, created_at, in_reply_to_id}]'
```

`/pulls/comments/XXX` 形式でPR番号が取れない場合はコメント取得後に `pull_request_url` からPR番号を抽出する:
```bash
gh api repos/<owner>/<repo>/pulls/comments/<comment-id> \
  --jq '{id, reviewer: .user.login, path, line, body, url: .html_url, in_reply_to_id, pr_number: (.pull_request_url | split("/") | last | tonumber)}'
```

### Step 3: コメントを整理して表示する

取得したコメントを以下の形式でユーザーに表示する:

```
## レビューコメント一覧

### [レビュアー名] - [CHANGES_REQUESTED / COMMENTED]
> [レビュー全体コメントがあれば表示]

#### 📄 [ファイルパス] L[行番号]
```diff
[diff_hunk]
```
**コメント**: [body]
**URL**: [html_url]
**スレッドID**: [id]
```

- `in_reply_to_id` があるコメントはスレッドとしてグループ化してインデントで表示
- レビュアー名フィルタが指定されている場合は該当レビュアーのコメントのみ表示
- コメントURLフィルタが指定されている場合は該当スレッドのみ表示
- **引数なし（全件対象）の場合も、`[bot]` サフィックスを持つレビュアーのコメントはデフォルトで除外する**（renovate, greptile-apps[bot] など。ボットコメントは通常対応不要なため）

### Step 4: 各コメントへの対応方針を決定する

各コメントについて、以下の基準で対応方針を判断する:

| 判断基準 | 対応 |
|---------|------|
| コードの修正が必要な指摘 | → コード修正してから返信 |
| 設計の議論・提案 | → **必ず** `AskUserQuestion` でユーザーに採用可否を確認してから返信 |
| 質問・確認事項 | → 回答を返信 |
| 既に対応済み・議論不要 | → その旨を返信 |

対応方針を決定したら、次のステップに進む前に **各コメントについて「[ファイルパス L行番号] → [対応方針と理由]」の形でユーザーに提示して確認を取る**。サイレントに実装を始めない。

### Step 5: コードを修正する（必要な場合）

- 対象ファイルを `Read` で読み込み、指摘箇所を特定して `Edit` で修正
- 修正後は以下の手順でパッケージマネージャーを自動判定してチェックを実行する:

```bash
if [ -f bun.lockb ] || [ -f bun.lock ] || grep -q '"packageManager".*bun' package.json 2>/dev/null; then
  PM="bun"
elif [ -f pnpm-lock.yaml ] || grep -q '"packageManager".*pnpm' package.json 2>/dev/null; then
  PM="pnpm"
elif [ -f yarn.lock ]; then
  PM="yarn"
else
  PM="npm"
fi
$PM run check
```

判定が難しい場合はルートの `package.json` の `"packageManager"` フィールドを直接 Read して確認する。

### Step 6: レビューコメントに返信する

`in_reply_to_id` にはスレッドの **root コメント ID** を指定する。GitHub PR コメントの `in_reply_to_id` フィールドは常に root コメントIDを指す（多段ネストなし）ため、`in_reply_to_id == null` のコメントが root、`in_reply_to_id != null` の場合はその値が root ID になる。返信コメントのIDを使うとスレッドが分断されるので注意。

```bash
# インラインコマントへの返信
gh api repos/<owner>/<repo>/pulls/<number>/comments \
  --method POST \
  -f body="<返信内容>" \
  -F in_reply_to_id=<rootコメントのid>

# レビュー全体への返信（PRのissueコメントとして投稿）
gh api repos/<owner>/<repo>/issues/<number>/comments \
  --method POST \
  -f body="<返信内容>"
```

返信内容のガイドライン:
- コード修正した場合: 「修正しました。[変更内容の簡潔な説明]」
- 採用しない場合: 「ご指摘ありがとうございます。[理由]のため、今回は対応を見送ります。」
- 質問への回答: 「[回答内容]」
- 返信は日本語で行う（相手が英語の場合は英語でも可）

### Step 7: 完了報告

```
## 対応完了

### 修正したファイル
- [ファイルパス]: [修正内容]

### 返信したコメント
- [コメントURL]: [対応内容]

### 対応不要だったコメント
- [コメントURL]: [理由]
```

}}
