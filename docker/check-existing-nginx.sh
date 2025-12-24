#!/bin/bash

# 检查现有 Nginx 配置脚本
# 用于检查服务器上是否已有其他项目运行

echo "=========================================="
echo "检查现有 Nginx 配置"
echo "=========================================="
echo ""

# 检查 Nginx 是否运行
if systemctl is-active --quiet nginx 2>/dev/null || pgrep nginx > /dev/null; then
    echo "✓ Nginx 正在运行"
    echo ""
    
    # 检查 Nginx 配置文件位置
    echo "检查 Nginx 配置文件位置..."
    if [ -d "/etc/nginx/conf.d" ]; then
        echo "✓ 检测到 CentOS/RHEL 配置结构: /etc/nginx/conf.d/"
        CONFIG_DIR="/etc/nginx/conf.d"
    elif [ -d "/etc/nginx/sites-available" ]; then
        echo "✓ 检测到 Debian/Ubuntu 配置结构: /etc/nginx/sites-available/"
        CONFIG_DIR="/etc/nginx/sites-available"
    else
        echo "⚠ 未找到标准配置目录"
        CONFIG_DIR=""
    fi
    
    echo ""
    echo "现有的 Nginx 配置文件:"
    if [ -n "$CONFIG_DIR" ]; then
        ls -la "$CONFIG_DIR"/*.conf 2>/dev/null | head -10 || echo "  未找到配置文件"
    fi
    
    echo ""
    echo "检查监听的端口..."
    sudo netstat -tulpn | grep nginx | grep LISTEN || sudo ss -tulpn | grep nginx | grep LISTEN || echo "  无法获取端口信息"
    
    echo ""
    echo "检查已配置的域名..."
    if [ -n "$CONFIG_DIR" ]; then
        grep -r "server_name" "$CONFIG_DIR"/*.conf 2>/dev/null | grep -v "^#" | head -10 || echo "  未找到域名配置"
    fi
    
    echo ""
    echo "=========================================="
    echo "建议："
    echo "=========================================="
    echo "1. 多个子域名可以指向同一个 IP，不会冲突"
    echo "2. Nginx 会根据请求的域名（Host header）路由到不同的配置"
    echo "3. 确保每个域名都有独立的 server 块配置"
    echo ""
    echo "如果 deepalpha 项目已经在运行，您需要："
    echo "1. 在现有 Nginx 配置中添加新的 server 块"
    echo "2. 或者使用 Docker Compose 的 Nginx 统一管理所有站点"
    echo ""
else
    echo "ℹ Nginx 未运行"
    echo ""
    echo "这意味着："
    echo "1. deepalpha 项目可能使用其他 Web 服务器（如 Apache）"
    echo "2. 或者 deepalpha 项目也在 Docker 中运行"
    echo "3. 或者 80 端口被其他服务占用"
    echo ""
    echo "检查占用 80 端口的进程:"
    sudo lsof -i :80 2>/dev/null || sudo netstat -tulpn | grep ":80 " || sudo ss -tulpn | grep ":80 " || echo "  无法检查"
fi

echo ""

