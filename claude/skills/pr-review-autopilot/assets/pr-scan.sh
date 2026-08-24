#!/bin/bash
# 未解決レビュースレッドの中身（指摘者・パス・本文冒頭）を展開する。オンデマンド用。
# 監視が REVIEW_ARRIVED で起こしてきたあと、何を言われたのかを見るために使う。
set -u
SP="$(cd "$(dirname "$0")" && pwd)"
. "$SP/autopilot.env"
cd "$AP_REPO_DIR"
for n in ${@:-$AP_PRS}; do
  gh api graphql -f query='
  query($owner:String!,$repo:String!,$num:Int!){
    repository(owner:$owner,name:$repo){
      pullRequest(number:$num){
        number title isDraft mergeable reviewDecision headRefName baseRefName
        reviewThreads(first:100){ nodes { isResolved isOutdated
          comments(first:1){ nodes { author{login} body path } } } }
        commits(last:1){ nodes { commit { statusCheckRollup { state } } } }
      }
    }
  }' -F owner="$AP_OWNER" -F repo="$AP_REPO" -F num="$n" --jq '
    .data.repository.pullRequest as $p |
    ($p.reviewThreads.nodes | map(select(.isResolved==false))) as $un |
    "#\($p.number) base=\($p.baseRefName) decision=\($p.reviewDecision // "-") ci=\($p.commits.nodes[0].commit.statusCheckRollup.state // "-") 未解決=\($un|length) | \($p.title)",
    ( $un[:6] | .[] | "      └ [\(.comments.nodes[0].author.login)] \(.comments.nodes[0].path // "-") :: \((.comments.nodes[0].body // "") | gsub("\n";" ") | .[0:110])" )
  ' 2>/dev/null
done
