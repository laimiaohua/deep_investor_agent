#!/bin/bash

# 检查端口占用情况脚本

echo "=========================================="
echo "检查端口占用情况"
echo "=========================================="
echo ""

# 检查 80 端口
echo "检查 80 端口占用情况:"
if command -v lsof &> /dev/null; then
    sudo lsof -i :80 || echo "  未找到占用进程"
elif command -v netstat &> /dev/null; then
    sudo netstat -tulpn | grep ":80 " || echo "  未找到占用进程"
elif command -v ss &> /dev/null; then
    sudo ss -tulpn | grep ":80 " || echo "  未找到占用进程"
fi

echo ""

# 检查 443 端口
echo "检查 443 端口占用情况:"
if command -v lsof &> /dev/null; then
    sudo lsof -i :443 || echo "  未找到占用进程"
elif command -v netstat &> /dev/null; then
    sudo netstat -tulpn | grep ":443 " || echo "  未找到占用进程"
elif command -v ss &> /dev/null; then
    sudo ss -tulpn | grep ":443 " || echo "  未找到占用进程"
fi

echo ""

# 检查 8000 端口
echo "检查 8000 端口占用情况:"
if command -v lsof &> /dev/null; then
    sudo lsof -i :8000 || echo "  未找到占用进程"
elif command -v netstat &> /dev/null; then
    sudo netstat -tulpn | grep ":8000 " || echo "  未找到占用进程"
elif command -v ss &> /dev/null; then
    sudo ss -tulpn | grep ":8000 " || echo "  未找到占用进程"
fi

echo ""

# 检查是否有 Nginx 运行
echo "检查 Nginx 服务状态:"
if systemctl is-active --quiet nginx 2>/dev/null; then
    echo "  ✓ Nginx 正在运行"
    echo ""
    echo "  Nginx 配置文件位置:"
    if [ -d "/etc/nginx/conf.d" ]; then
        echo "    /etc/nginx/conf.d/"
        ls -la /etc/nginx/conf.d/*.conf 2>/dev/null | head -5
    elif [ -d "/etc/nginx/sites-available" ]; then
        echo "    /etc/nginx/sites-available/"
        ls -la /etc/nginx/sites-available/* 2>/dev/null | head -5
    fi
elif pgrep nginx > /dev/null; then
    echo "  ✓ Nginx 进程正在运行"
else
    echo "  ℹ Nginx 未运行"
fi

echo ""
echo "=========================================="
echo "建议解决方案:"
echo "=========================================="
echo ""
echo "如果 80 端口被占用，您可以选择："
echo ""
echo "方案1: 停止占用端口的服务（如果不需要）"
echo "  sudo systemctl stop nginx"
echo "  或"
echo "  sudo docker stop <container-name>"
echo ""
echo "方案2: 修改 Docker Compose 使用其他端口"
echo "  编辑 docker-compose.prod.yml，将端口映射改为："
echo "    ports:"
echo "      - \"8080:80\"   # HTTP"
echo "      - \"8443:443\"  # HTTPS"
echo ""
echo "方案3: 使用现有 Nginx 作为反向代理（推荐）"
echo "  配置现有 Nginx 代理到 Docker 容器的内部端口"
echo ""

