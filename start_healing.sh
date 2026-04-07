#!/bin/bash
# 自愈开发循环 - Tmux 后台启动脚本
# 使用方法: ./start_healing.sh [attach]

SESSION_NAME="dedao-healing"
PROJECT_DIR="/Users/fei/vscodeOpj/dedao-notebooklm"
SCRIPT_NAME="self_healing_loop.py"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          Dedao-dl 自愈开发循环 - 启动器                      ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# 检查是否已有session在运行
if tmux has-session -t $SESSION_NAME 2>/dev/null; then
    echo -e "${YELLOW}⚠️  自愈循环已在运行中${NC}"
    echo ""
    echo "要连接到会话查看进度:"
    echo -e "  ${GREEN}tmux attach -t $SESSION_NAME${NC}"
    echo ""
    echo "要停止会话:"
    echo -e "  ${RED}tmux kill-session -t $SESSION_NAME${NC}"
    echo ""

    # 如果参数是 attach，则连接到会话
    if [ "$1" = "attach" ] || [ "$1" = "-a" ]; then
        tmux attach -t $SESSION_NAME
    fi
    exit 0
fi

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ 未找到 python3${NC}"
    exit 1
fi

# 检查项目目录
if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${RED}❌ 项目目录不存在: $PROJECT_DIR${NC}"
    exit 1
fi

# 检查脚本文件
if [ ! -f "$PROJECT_DIR/$SCRIPT_NAME" ]; then
    echo -e "${RED}❌ 脚本文件不存在: $SCRIPT_NAME${NC}"
    exit 1
fi

echo -e "${GREEN}📁 项目目录:${NC} $PROJECT_DIR"
echo -e "${GREEN}🐍 Python:${NC} $(python3 --version)"
echo ""

# 创建tmux session
echo -e "${BLUE}🚀 启动自愈循环...${NC}"
tmux new-session -d -s $SESSION_NAME -c "$PROJECT_DIR"

# 设置环境
tmux send-keys -t $SESSION_NAME "cd $PROJECT_DIR" C-m
tmux send-keys -t $SESSION_NAME "source ~/.zshrc 2>/dev/null || source ~/.bashrc 2>/dev/null" C-m

# 运行自愈脚本
tmux send-keys -t $SESSION_NAME "python3 $SCRIPT_NAME 2>&1 | tee self_healing_logs/console.log" C-m

echo ""
echo -e "${GREEN}✅ 自愈循环已启动!${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${YELLOW}使用方法:${NC}"
echo ""
echo "  查看进度:"
echo -e "    ${GREEN}tmux attach -t $SESSION_NAME${NC}"
echo ""
echo "  退出查看 (不停止):"
echo -e "    ${BLUE}按 Ctrl+B 然后按 D${NC}"
echo ""
echo "  停止循环:"
echo -e "    ${RED}tmux kill-session -t $SESSION_NAME${NC}"
echo ""
echo "  查看日志:"
echo -e "    ${BLUE}tail -f $PROJECT_DIR/self_healing_logs/self_healing.log${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 如果参数是 attach，则自动连接
if [ "$1" = "attach" ] || [ "$1" = "-a" ]; then
    echo ""
    echo -e "${BLUE}连接到会话...${NC}"
    sleep 1
    tmux attach -t $SESSION_NAME
fi
