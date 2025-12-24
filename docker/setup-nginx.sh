#!/bin/bash

# Nginx 配置脚本
# 用于配置外部 Nginx 作为反向代理

set -e

DOMAIN="deepinvestoragent.gravitechinnovations.com"
NGINX_CONF_DIR=""
NGINX_CONF_FILE=""

echo "=========================================="
echo "Nginx 配置脚本"
echo "域名: ${DOMAIN}"
echo "=========================================="
echo ""

# 检测系统类型和 Nginx 配置目录
if [ -d "/etc/nginx/conf.d" ]; then
    NGINX_CONF_DIR="/etc/nginx/conf.d"
    NGINX_CONF_FILE="${NGINX_CONF_DIR}/deepinvestoragent.conf"
    echo "检测到 CentOS/RHEL/OpenCloudOS 系统"
elif [ -d "/etc/nginx/sites-available" ]; then
    NGINX_CONF_DIR="/etc/nginx/sites-available"
    NGINX_CONF_FILE="${NGINX_CONF_DIR}/deepinvestoragent.conf"
    echo "检测到 Debian/Ubuntu 系统"
else
    echo "错误: 未找到 Nginx 配置目录"
    echo "请确保 Nginx 已安装"
    exit 1
fi

echo "配置文件位置: ${NGINX_CONF_FILE}"
echo ""

# 检查 Nginx 是否安装
if ! command -v nginx &> /dev/null && ! systemctl list-unit-files | grep -q nginx; then
    echo "警告: 未检测到 Nginx，请先安装 Nginx"
    echo ""
    echo "CentOS/RHEL/OpenCloudOS:"
    echo "  sudo yum install -y nginx"
    echo ""
    echo "Debian/Ubuntu:"
    echo "  sudo apt install -y nginx"
    exit 1
fi

# 检查 Docker 服务是否运行
echo "检查 Docker 服务状态..."
if ! docker ps | grep -q deep-investor-agent-backend; then
    echo "警告: Docker 后端服务未运行"
    echo "请先运行: cd docker && ./deploy-no-nginx.sh"
    echo ""
    read -p "是否继续配置 Nginx? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 检查端口是否监听
echo "检查服务端口..."
if ! ss -tuln | grep -q ":8000 " && ! netstat -tuln | grep -q ":8000 "; then
    echo "警告: 端口 8000 未监听，后端服务可能未启动"
fi

if ! ss -tuln | grep -q ":8080 " && ! netstat -tuln | grep -q ":8080 "; then
    echo "警告: 端口 8080 未监听，前端服务可能未启动"
fi

echo ""

# 检查 SSL 证书
SSL_CERT="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
SSL_KEY="/etc/letsencrypt/live/${DOMAIN}/privkey.pem"

if [ ! -f "$SSL_CERT" ] || [ ! -f "$SSL_KEY" ]; then
    echo "警告: SSL 证书不存在"
    echo "证书路径:"
    echo "  - ${SSL_CERT}"
    echo "  - ${SSL_KEY}"
    echo ""
    echo "如果需要获取 SSL 证书，运行:"
    echo "  cd docker && sudo ./setup-ssl.sh"
    echo ""
    read -p "是否继续配置（将使用 HTTP）? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    USE_SSL=false
else
    echo "✓ SSL 证书存在"
    USE_SSL=true
fi

echo ""

# 复制配置文件
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_FILE="${SCRIPT_DIR}/nginx-external.conf.example"

if [ ! -f "$TEMPLATE_FILE" ]; then
    echo "错误: 找不到配置模板文件"
    echo "路径: ${TEMPLATE_FILE}"
    exit 1
fi

echo "复制配置文件..."
sudo cp "$TEMPLATE_FILE" "$NGINX_CONF_FILE"
echo "✓ 配置文件已复制到: ${NGINX_CONF_FILE}"

# 如果是 Debian/Ubuntu，创建符号链接
if [ -d "/etc/nginx/sites-enabled" ]; then
    if [ ! -L "/etc/nginx/sites-enabled/deepinvestoragent.conf" ]; then
        sudo ln -s "$NGINX_CONF_FILE" /etc/nginx/sites-enabled/deepinvestoragent.conf
        echo "✓ 已创建符号链接"
    fi
fi

echo ""
echo "=========================================="
echo "配置文件已创建"
echo "=========================================="
echo ""
echo "下一步："
echo ""
echo "1. 编辑配置文件:"
echo "   sudo nano ${NGINX_CONF_FILE}"
echo ""
echo "2. 确认以下配置:"
echo "   - SSL 证书路径（如果使用 HTTPS）"
echo "   - 后端端口: 127.0.0.1:8000"
echo "   - 前端端口: 127.0.0.1:8080"
echo ""
echo "3. 测试配置:"
echo "   sudo nginx -t"
echo ""
echo "4. 重载 Nginx:"
echo "   sudo systemctl reload nginx"
echo ""
echo "5. 验证部署:"
echo "   curl https://${DOMAIN}/api/health"
echo ""

