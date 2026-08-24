#!/usr/bin/env python3
"""担当 PR の状態を 1 行 1 PR で出す。

出力: <番号> <未解決スレッド> <他人の issue コメント> <approve数> <base> <mergeable> <CI>

固定長のスペース区切りにしているのは、シェルの `while read` でそのまま読めるからである。
JSON にすると jq を挟む必要があり、state ファイルとの差分比較も面倒になる。
"""
import json
import os
import re
import subprocess

OWNER = os.environ["AP_OWNER"]
REPO = os.environ["AP_REPO"]
REPO_DIR = os.environ["AP_REPO_DIR"]
SELF = os.environ["AP_SELF"]
BOT = re.compile(os.environ.get("AP_BOTS") or r"(?!x)x", re.I)
PRS = [int(x) for x in os.environ["AP_PRS"].split()]

Q = """query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){pullRequest(number:$n){
  state baseRefName mergeable
  commits(last:1){nodes{commit{statusCheckRollup{state}}}}
  reviewThreads(first:100){nodes{isResolved}}
  comments(last:40){nodes{author{login}}}
  latestReviews(first:20){nodes{author{login} state}}}}}"""

for n in PRS:
    try:
        out = subprocess.run(
            ["gh", "api", "graphql", "-f", f"query={Q}",
             "-F", f"o={OWNER}", "-F", f"r={REPO}", "-F", f"n={n}"],
            capture_output=True, timeout=40, cwd=REPO_DIR)
        p = json.loads(out.stdout)["data"]["repository"]["pullRequest"]
    except Exception:
        # 取得できなかった PR は「行を出さない」。
        # 0 を出すと「減った」と誤検知され、次のサイクルで「増えた」と二重に鳴る。
        continue
    if p["state"] != "OPEN":
        continue
    th = sum(1 for x in p["reviewThreads"]["nodes"] if not x["isResolved"])
    cm = sum(1 for c in p["comments"]["nodes"]
             if (c.get("author") or {}).get("login") not in (None, SELF)
             and not BOT.search((c.get("author") or {}).get("login", "")))
    # 自分と bot の approve は数えない。自分の approve でマージが走ったら事故。
    ap = len({r["author"]["login"] for r in p["latestReviews"]["nodes"]
              if r["state"] == "APPROVED"
              and r["author"]["login"] != SELF
              and not BOT.search(r["author"]["login"])})
    try:
        ci = p["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["state"]
    except Exception:
        ci = "NONE"
    print(f'{n} {th} {cm} {ap} {p["baseRefName"]} {p["mergeable"]} {ci}')
