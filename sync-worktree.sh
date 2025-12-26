#!/bin/bash

# Worktree 同步脚本
# 用于将 worktree 的更改同步到主项目
# 解决 Cursor 路径解析错误的问题

WORKTREE_PATH="/Users/laimiaohua/.cursor/worktrees/gravitech_deep_investor_agent/cjz"
MAIN_PATH="/Users/laimiaohua/Appproject/gravitech_deep_investor_agent"

echo "开始同步 worktree 更改到主项目..."

# 需要同步的文件列表
FILES=(
    "app/frontend/src/components/panels/left/flow-context-menu.tsx"
    "app/frontend/src/nodes/components/agent-output-dialog.tsx"
    "app/frontend/src/nodes/components/json-output-dialog.tsx"
    "app/frontend/src/components/ui/dialog.tsx"
)

# 同步每个文件
for file in "${FILES[@]}"; do
    worktree_file="${WORKTREE_PATH}/${file}"
    main_file="${MAIN_PATH}/${file}"
    
    if [ -f "$worktree_file" ]; then
        echo "同步: $file"
        cp "$worktree_file" "$main_file"
    else
        echo "警告: 文件不存在 $worktree_file"
    fi
done

echo "同步完成！"
echo ""
echo "检查差异..."
cd "$MAIN_PATH"
git status

