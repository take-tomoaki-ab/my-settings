#!/bin/bash
# PR レビュー対応の自律運転 — 監視ループ。
#
# ポーリングではない。「起こすべき状態」を検知したら exit 0 で終了する。
# Claude Code のバックグラウンドコマンドが終了するとハーネスがセッションを再呼び出しするので、
# それがオーケストレーターの起床トリガーになる。
#
# 起床条件（優先順）:
#   1. READY_TO_MERGE      base=main / approve>=N / 未解決 0 / MERGEABLE / CI SUCCESS の全成立
#   2. PANE_FREE_WITH_QUEUE 投入できる待ち行列がある状態でペインが空いた
#   3. REVIEW_ARRIVED      未解決スレッド or 他人の issue コメントが「増えた」
#   4. NEEDS_CONFLICT_FIX  approve 済みなのに CONFLICTING、かつ未タスク化
#   5. STALL               doing なのに claude プロセスが死んでいる
#
# 🔴 「状態」だけで起こしてはいけない。必ず「まだ対応していない」を組み合わせる。
#    状態ベースの条件は、その状態が続く限り毎サイクル鳴り続ける。
#
# 使い方: bash review-watch.sh [監視間隔秒=180] [最大稼働分=720]

set -u
SP="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
. "$SP/autopilot.env"

IV="${1:-180}"
MAXMIN="${2:-720}"
STATE="$SP/review-watch.state"
LOCK="$SP/review-watch.lock"
BASE_BRANCH="${AP_BASE_BRANCH:-main}"
MIN_APPROVE="${AP_MIN_APPROVE:-1}"
PANE_TOTAL="${AP_PANE_TOTAL:-2}"

# --- 二重起動の防止 ---
# 複数の監視が同じ state を書くと、片方が変化を食べてもう片方が検知を取りこぼす。
# 起動経路は必ず 1 系統に統一する（`&` と run_in_background の併用が事故の原因になった）。
if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  echo "ALREADY_RUNNING pid=$(cat "$LOCK")"; exit 4
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

DEADLINE=$(( $(date +%s) + MAXMIN * 60 ))

# state が無ければ現在値で初期化する。
# 初回から差分を出すと、既に来ているレビューで即起床して意味が無い。
[ -f "$STATE" ] || python3 "$SP/snapshot.py" > "$STATE"

# タスクキューへの問い合わせ。AP_DB が空なら何も返さない（キュー連携なしで動く）。
q() { [ -n "${AP_DB:-}" ] && sqlite3 "$AP_DB" "$1" 2>/dev/null; }
IN_REPO="json_extract(data,'\$.repoId')='${AP_REPO_ID:-}'"

while :; do
  NOW=$(python3 "$SP/snapshot.py")
  # 全 PR の取得に失敗したときは state を上書きしない。壊れた state で誤検知するのを防ぐ。
  [ -z "$NOW" ] && { sleep "$IV"; continue; }

  # --- 1. マージ可能: 5 条件すべて ---
  MERGEABLE_NOW=""
  while read -r n th cm ap base mrg ci; do
    [ "$base" = "$BASE_BRANCH" ] \
      && [ "${ap:-0}" -ge "$MIN_APPROVE" ] 2>/dev/null \
      && [ "${th:-1}" -eq 0 ] 2>/dev/null \
      && [ "$mrg" = "MERGEABLE" ] && [ "$ci" = "SUCCESS" ] \
      && MERGEABLE_NOW="$MERGEABLE_NOW #$n(approve=$ap)"
  done <<< "$NOW"

  # --- 3. レビュー着弾: 「増えた」ときだけ ---
  # 減少では起こさない。7 → 1 は対応が進んだ証拠であって、対応すべき事象ではない。
  HIT=""
  while read -r n th cm ap base mrg ci; do
    old=$(grep "^$n " "$STATE")
    [ -z "$old" ] && continue
    oth=$(echo "$old" | awk '{print $2}')
    ocm=$(echo "$old" | awk '{print $3}')
    [ "$th" -gt "$oth" ] 2>/dev/null && HIT="$HIT NEW_THREAD:#$n(${oth}→${th})"
    [ "$cm" -gt "$ocm" ] 2>/dev/null && HIT="$HIT NEW_COMMENT:#$n(${ocm}→${cm})"
  done <<< "$NOW"

  # --- 4. approve 済み × CONFLICTING ---
  # 🔴 「まだタスク化していない」を必ず組み合わせる。
  #    これを忘れると、衝突が解消されるまで毎サイクル鳴る（実際にやった）。
  NEEDS_FIX=""
  while read -r n th cm ap base mrg ci; do
    [ "${ap:-0}" -ge "$MIN_APPROVE" ] 2>/dev/null && [ "$mrg" = "CONFLICTING" ] || continue
    HANDLED=$(q "select count(*) from tasks
      where status in ('will_do','doing') and $IN_REPO and title like '%#$n%'")
    [ "${HANDLED:-0}" -eq 0 ] 2>/dev/null \
      && NEEDS_FIX="$NEEDS_FIX #$n(approve=$ap,base=$base)"
  done <<< "$NOW"

  # --- 2. 待ち行列 × 空きペイン ---
  # 「投入できるものを列挙」ではなく「投入できないものを除外」で書く。
  # 新しく作ったタスクが黙って無視されるより、余分に起こされるほうがマシ。
  EXCL="${AP_QUEUE_EXCLUDE:-1=1}"
  QUEUED=$(q "select count(*) from tasks where status='will_do' and $IN_REPO and ($EXCL)")
  BUSY=$(q "select count(*) from tasks where status='doing' and $IN_REPO and pane in ('main','sub')")
  FREE=$(( PANE_TOTAL - ${BUSY:-PANE_TOTAL} ))

  # --- 5. 突然死 ---
  # pid は tasks.data ではなく task_runtime にある。
  # ここを間違えると「一度も発火しない条件」になり、バグに気づけない。
  STALL=""
  while IFS='|' read -r title pid; do
    [ -z "$pid" ] && continue
    kill -0 "$pid" 2>/dev/null || STALL="$STALL [$title]"
  done < <(q "select t.title||'|'||coalesce(r.pid,'') from tasks t
    left join task_runtime r on r.task_id=t.id
    where t.status='doing' and json_extract(t.data,'\$.repoId')='${AP_REPO_ID:-}'
      and t.pane in ('main','sub')")

  echo "[$(date +%H:%M:%S)] $(echo "$NOW" | awk '{printf "#%s:%s/%s/ap%s ", $1,$2,$3,$4}')"
  echo "$NOW" > "$STATE"

  [ -n "$MERGEABLE_NOW" ] && { echo "READY_TO_MERGE$MERGEABLE_NOW"; exit 0; }
  [ "${QUEUED:-0}" -gt 0 ] 2>/dev/null && [ "$FREE" -gt 0 ] 2>/dev/null \
    && { echo "PANE_FREE_WITH_QUEUE 空き=$FREE 待ち=$QUEUED"; exit 0; }
  [ -n "$HIT" ]       && { echo "REVIEW_ARRIVED$HIT"; exit 0; }
  [ -n "$NEEDS_FIX" ] && { echo "NEEDS_CONFLICT_FIX$NEEDS_FIX"; exit 0; }
  [ -n "$STALL" ]     && { echo "STALL$STALL"; exit 0; }
  [ "$(date +%s)" -gt "$DEADLINE" ] && { echo "TIMEOUT"; exit 3; }
  sleep "$IV"
done
