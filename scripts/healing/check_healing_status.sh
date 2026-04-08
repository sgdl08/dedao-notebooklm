#!/bin/bash
# 自愈开发循环 - 状态检查脚本
# 使用方法: ./check_healing_status.sh

PROJECT_DIR="/Users/fei/vscodeOpj/dedao-notebooklm"
PID_FILE="$PROJECT_DIR/self_healing.pid"
LOG_FILE="$PROJECT_DIR/self_healing_logs/console.log"
STATE_FILE="$PROJECT_DIR/.self_healing_state.json"
REPORTS_DIR="$PROJECT_DIR/self_healing_logs"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║          Dedao-dl 自愈开发循环 - 状态检查                    ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# 检查进程状态
echo -e "${BLUE}📊 进程状态${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo -e "状态: ${GREEN}● 运行中${NC}"
        echo "PID: $PID"
        # 显示进程运行时间
        ELAPSED=$(ps -o etime= -p "$PID" 2>/dev/null | tr -d ' ')
        echo "运行时间: $ELAPSED"
    else
        echo -e "状态: ${YELLOW}● 已完成${NC}"
        rm -f "$PID_FILE"
    fi
else
    echo -e "状态: ${CYAN}● 未运行${NC}"
fi

echo ""

# 显示状态文件内容
if [ -f "$STATE_FILE" ]; then
    echo -e "${BLUE}📈 迭代状态${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # 使用Python读取JSON（更可靠）
    python3 -c "
import json
from pathlib import Path

state_file = Path('$STATE_FILE')
if state_file.exists():
    data = json.loads(state_file.read_text())
    print(f\"当前迭代: {data.get('current_iteration', 0)}\")
    print(f\"累计失败: {data.get('total_failures', 0)}\")
    print(f\"已修复: {data.get('fixed_issues', 0)}\")
    print(f\"剩余问题: {len(data.get('remaining_issues', []))}\")
" 2>/dev/null || cat "$STATE_FILE"

    echo ""
fi

# 显示最近的迭代报告
REPORTS=$(ls -1 "$REPORTS_DIR"/iteration_*_report.md 2>/dev/null | tail -3)
if [ -n "$REPORTS" ]; then
    echo -e "${BLUE}📋 最近报告${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    for report in $REPORTS; do
        filename=$(basename "$report")
        echo -e "  ${GREEN}● ${filename}${NC}"
    done
    echo ""
fi

# 显示最后10行日志
if [ -f "$LOG_FILE" ]; then
    echo -e "${BLUE}📝 最近日志${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    tail -10 "$LOG_FILE"
    echo ""
fi

# 快捷命令提示
echo -e "${YELLOW}快捷命令${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  查看完整日志:"
echo -e "    ${GREEN}tail -f $LOG_FILE${NC}"
echo ""
echo "  查看报告:"
echo -e "    ${GREEN}cat $REPORTS_DIR/iteration_1_report.md${NC}"
echo ""
echo "  重新运行:"
echo -e "    ${GREEN}cd $PROJECT_DIR && python3 self_healing_loop.py${NC}"
echo ""
