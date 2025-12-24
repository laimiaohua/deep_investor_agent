#!/bin/bash

# 不使用 Docker Nginx 的部署脚本
# 适用于服务器上已有 Nginx 运行的情况
# 使用方法: ./deploy-no-nginx.sh

set -e

echo "=========================================="
echo "Deep Investor Agent 部署脚本（无 Nginx）"
echo "=========================================="

# 检查 Docker 和 Docker Compose 是否安装
if ! command -v docker &> /dev/null; then
    echo "错误: Docker 未安装，请先安装 Docker"
    exit 1
fi

# 检测 Docker Compose 命令
DOCKER_COMPOSE_CMD=""
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
    echo "使用 docker-compose 命令"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
    echo "使用 docker compose 命令"
else
    echo "错误: Docker Compose 未安装"
    exit 1
fi

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.prod-no-nginx.yml"

# 检查 compose 文件是否存在
if [ ! -f "$COMPOSE_FILE" ]; then
    echo "错误: 找不到 docker-compose.prod-no-nginx.yml 文件"
    echo "文件路径: $COMPOSE_FILE"
    echo ""
    echo "请确保文件已同步到服务器，或手动创建该文件"
    echo "文件位置应该在: $(dirname "$SCRIPT_DIR")/docker/docker-compose.prod-no-nginx.yml"
    exit 1
fi

echo "使用配置文件: $COMPOSE_FILE"

# 检查 .env 文件是否存在
if [ ! -f "../.env" ]; then
    echo "警告: .env 文件不存在，请确保在生产服务器上创建 .env 文件"
    echo "提示: 可以复制 .env.example 并修改配置"
fi

# 创建必要的目录
echo "创建必要的目录..."
mkdir -p ../logs

# 停止现有容器
echo "停止现有容器..."
$DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" down || true

# 构建镜像
echo "构建 Docker 镜像..."
$DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" build --no-cache

# 启动服务
echo "启动服务..."
$DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" up -d

# 等待服务启动
echo "等待服务启动..."
sleep 10

# 检查服务状态
echo "检查服务状态..."
$DOCKER_COMPOSE_CMD -f "$COMPOSE_FILE" ps

echo ""
echo "=========================================="
echo "Docker 服务部署完成！"
echo "=========================================="
echo ""
echo "服务端口:"
echo "  - 后端 API: http://localhost:8000"
echo "  - 前端应用: http://localhost:8080"
echo ""
echo "下一步：配置外部 Nginx 反向代理"
echo ""
echo "1. 复制 Nginx 配置:"
echo "   sudo cp docker/nginx-external.conf.example /etc/nginx/conf.d/deepinvestoragent.conf"
echo ""
echo "2. 编辑配置（根据实际情况调整）:"
echo "   sudo nano /etc/nginx/conf.d/deepinvestoragent.conf"
echo ""
echo "3. 测试并重载 Nginx:"
echo "   sudo nginx -t"
echo "   sudo systemctl reload nginx"
echo ""
echo "查看日志:"
echo "  $DOCKER_COMPOSE_CMD -f $COMPOSE_FILE logs -f"
echo ""
echo "停止服务:"
echo "  $DOCKER_COMPOSE_CMD -f $COMPOSE_FILE down"
echo ""

