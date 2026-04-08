#!/bin/bash
# 自愈开发循环 - 后台启动脚本 (nohup 版本)
# 使用方法: ./start_healing_bg.sh

PROJECT_DIR="/Users/fei/vscodeOpj/dedao-notebooklm"
SCRIPT_NAME="self_healing_loop.py"
PID_FILE="$PROJECT_DIR/self_healing.pid"
LOG_FILE="$PROJECT_DIR/self_healing_logs/console.log"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          Dedao-dl 自愈开发循环 - 后台启动器                  ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# 检查是否已在运行
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  自愈循环已在运行中 (PID: $OLD_PID)${NC}"
        echo ""
        echo "查看日志:"
        echo -e "  ${GREEN}tail -f $LOG_FILE${NC}"
        echo ""
        echo "停止循环:"
        echo -e "  ${RED}kill $OLD_PID && rm $PID_FILE${NC}"
        exit 0
    else
        rm -f "$PID_FILE"
    fi
fi

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ 未找到 python3${NC}"
    exit 1
fi

# 确保日志目录存在
mkdir -p "$PROJECT_DIR/self_healing_logs"

echo -e "${GREEN}📁 项目目录:${NC} $PROJECT_DIR"
echo -e "${GREEN}🐍 Python:${NC} $(python3 --version)"
echo ""

# 启动后台进程
echo -e "${BLUE}🚀 启动自愈循环 (后台模式)...${NC}"

cd "$PROJECT_DIR"
nohup python3 "$SCRIPT_NAME" > "$LOG_FILE" 2>&1 &
PID=$!
echo $PID > "$PID_FILE"

sleep 1

# 检查是否启动成功
if ps -p "$PID" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ 自愈循环已启动! (PID: $PID)${NC}"
else
    echo -e "${RED}❌ 启动失败，请检查日志${NC}"
    rm -f "$PID_FILE"
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${YELLOW}使用方法:${NC}"
echo ""
echo "  查看实时日志:"
echo -e "    ${GREEN}tail -f $LOG_FILE${NC}"
echo ""
echo "  查看迭代报告:"
echo -e "    ${BLUE}ls -la $PROJECT_DIR/self_healing_logs/${NC}"
echo ""
echo "  停止循环:"
echo -e "    ${RED}kill $PID${NC}"
echo "    ${RED}rm $PID_FILE${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 显示初始日志
echo ""
echo -e "${BLUE}📋 初始输出:${NC}"
sleep 2
head -30 "$LOG_FILE" 2>/dev/null || echo "(等待输出...)"
