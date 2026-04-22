alias ccd="claude --dangerously-skip-permissions"

# git-ai-commit: claude -p でコミットメッセージを生成
export PATH="$HOME/Desktop/codes/my-settings/bin:$PATH"
alias gaic='git-ai-commit'           # 生成 → 確認後コミット
alias gaicn='git-ai-commit --dry-run' # メッセージ表示のみ
alias gaicy='git-ai-commit --yes'    # 生成 → 即コミット