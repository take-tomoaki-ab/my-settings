#!/bin/bash
# オンデマンドのダッシュボード。起床時に「今どうなっているか」を一目で見るためのもの。
# 監視ループとは独立。判断材料が欲しくなったときに手で叩く。
set -u
SP="$(cd "$(dirname "$0")" && pwd)"
. "$SP/autopilot.env"
IN_REPO="json_extract(data,'\$.repoId')='${AP_REPO_ID:-}'"
q() { [ -n "${AP_DB:-}" ] && sqlite3 "$AP_DB" "$1" 2>/dev/null; }

echo "### ペイン占有 ###"
q "select '  '||coalesce(nullif(pane,''),'(なし)')||'  '||status||'  '||title
   from tasks where status='doing' and $IN_REPO"
BUSY=$(q "select count(*) from tasks where status='doing' and $IN_REPO and pane in ('main','sub')")
echo "  → 空きペイン数: $(( ${AP_PANE_TOTAL:-2} - ${BUSY:-0} ))"
echo
echo "### PR の状態（未解決 / approve / base / mergeable / CI） ###"
python3 "$SP/snapshot.py" | awk '{printf "  #%-5s 未解決=%-3s 他人コメント=%-3s approve=%-3s base=%-28s %s / %s\n",$1,$2,$3,$4,$5,$6,$7}'
echo
echo "### 未返信の issue コメント（reviewThreads に出ないもの） ###"
"$SP/issue-comments.sh" 2>/dev/null || echo "  (なし)"
echo
echo "### 未着手タスク ###"
q "select '  '||title from tasks where status='will_do' and $IN_REPO"
