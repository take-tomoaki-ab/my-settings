#!/bin/bash
# reviewThreads に出ない issue レベルのコメントのうち、bot でも自分でもないものを全件出す。
# タイムスタンプでの「対応済み」自動判定はしない。別件の返信で未対応が埋もれるため、目視で判断する。
set -u
SP="$(cd "$(dirname "$0")" && pwd)"
. "$SP/autopilot.env"
cd "$AP_REPO_DIR"
for n in ${@:-$AP_PRS}; do
  gh api graphql -f query='query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){pullRequest(number:$n){comments(last:40){nodes{author{login} createdAt url body}}}}}' \
    -F o="$AP_OWNER" -F r="$AP_REPO" -F n="$n" \
    --jq '.data.repository.pullRequest.comments.nodes' 2>/dev/null \
  | AP_N="$n" python3 -c "
import sys, os, json, re
n = os.environ['AP_N']
try:
    cs = json.load(sys.stdin) or []
except Exception:
    sys.exit()
BOT = re.compile(os.environ.get('AP_BOTS') or r'(?!x)x', re.I)
SELF = os.environ['AP_SELF']
for c in cs:
    a = (c.get('author') or {}).get('login', '')
    if not a or a == SELF or BOT.search(a):
        continue
    body = ' '.join(c['body'].split())
    print(f\"  #{n} [{a}] {c['createdAt'][5:16]} :: {body[:130]}\")
"
done
