#!/bin/bash

# 生产环境部署脚本
# 使用方法: ./deploy.sh

set -e

echo "=========================================="
echo "Deep Investor Agent 生产环境部署脚本"
echo "=========================================="

# 检查 Docker 和 Docker Compose 是否安装
if ! command -v docker &> /dev/null; then
    echo "错误: Docker 未安装，请先安装 Docker"
    exit 1
fi

# 检测 Docker Compose 命令（支持 docker-compose 和 docker compose）
DOCKER_COMPOSE_CMD=""
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
    echo "使用 docker-compose 命令"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
    echo "使用 docker compose 命令"
else
    echo "错误: Docker Compose 未安装，请先安装 Docker Compose"
    echo "安装方法:"
    echo "  sudo yum install -y docker-compose-plugin"
    echo "  或"
    echo "  sudo curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)\" -o /usr/local/bin/docker-compose"
    echo "  sudo chmod +x /usr/local/bin/docker-compose"
    exit 1
fi

# 检查 .env 文件是否存在
if [ ! -f "../.env" ]; then
    echo "警告: .env 文件不存在，请确保在生产服务器上创建 .env 文件"
    echo "提示: 可以复制 .env.example 并修改配置"
fi

# 检查 SSL 证书
if [ ! -f "./nginx/ssl/fullchain.pem" ] || [ ! -f "./nginx/ssl/privkey.pem" ]; then
    echo "警告: SSL 证书文件不存在"
    echo "请将 SSL 证书放置在以下位置:"
    echo "  - ./nginx/ssl/fullchain.pem"
    echo "  - ./nginx/ssl/privkey.pem"
    echo ""
    echo "如果需要使用 Let's Encrypt，可以运行:"
    echo "  certbot certonly --standalone -d deepinvestoragent.gravitechinnovations.com"
    echo ""
    read -p "是否继续部署? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 创建必要的目录
echo "创建必要的目录..."
mkdir -p ./nginx/ssl
mkdir -p ./nginx/logs
mkdir -p ../logs

# 停止现有容器
echo "停止现有容器..."
$DOCKER_COMPOSE_CMD -f docker-compose.prod.yml down || true

# 构建镜像
echo "构建 Docker 镜像..."
$DOCKER_COMPOSE_CMD -f docker-compose.prod.yml build --no-cache

# 启动服务
echo "启动服务..."
$DOCKER_COMPOSE_CMD -f docker-compose.prod.yml up -d

# 等待服务启动
echo "等待服务启动..."
sleep 10

# 检查服务状态
echo "检查服务状态..."
$DOCKER_COMPOSE_CMD -f docker-compose.prod.yml ps

echo ""
echo "=========================================="
echo "部署完成！"
echo "=========================================="
echo ""
echo "服务访问地址:"
echo "  - 前端应用: https://deepinvestoragent.gravitechinnovations.com"
echo "  - API 文档: https://deepinvestoragent.gravitechinnovations.com/documentation"
echo ""
echo "查看日志:"
echo "  $DOCKER_COMPOSE_CMD -f docker-compose.prod.yml logs -f"
echo ""
echo "停止服务:"
echo "  $DOCKER_COMPOSE_CMD -f docker-compose.prod.yml down"
echo ""
echo "重启服务:"
echo "  $DOCKER_COMPOSE_CMD -f docker-compose.prod.yml restart"
echo ""

