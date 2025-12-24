#!/bin/bash

# 快速修复 Nginx 配置脚本

set -e

NGINX_CONF="/etc/nginx/conf.d/deepinvestoragent.conf"

echo "=========================================="
echo "修复 Nginx 配置"
echo "=========================================="
echo ""

if [ ! -f "$NGINX_CONF" ]; then
    echo "错误: 配置文件不存在: $NGINX_CONF"
    echo "请先运行: sudo ./setup-nginx.sh"
    exit 1
fi

echo "备份原配置..."
sudo cp "$NGINX_CONF" "${NGINX_CONF}.backup.$(date +%Y%m%d_%H%M%S)"

echo "更新配置..."

# 修复 http2 指令
sudo sed -i 's/listen 443 ssl http2;/listen 443 ssl;\n    http2 on;/' "$NGINX_CONF"

# 修复 API 代理路径
# 将 location /api { 改为 location /api/ {
sudo sed -i 's|location /api {|location /api/ {|' "$NGINX_CONF"

# 修复 proxy_pass，确保去掉 /api 前缀
sudo sed -i 's|proxy_pass http://deep_investor_backend;|proxy_pass http://deep_investor_backend/;|' "$NGINX_CONF"

# 添加 /api 重定向（如果不存在）
if ! grep -q "location = /api" "$NGINX_CONF"; then
    # 在 location /api/ 之前插入
    sudo sed -i '/location \/api\//i\    # 处理 /api（不带尾部斜杠）重定向到 /api/\n    location = /api {\n        return 301 $scheme://$host/api/;\n    }\n' "$NGINX_CONF"
fi

echo "✓ 配置已更新"
echo ""

# 测试配置
echo "测试 Nginx 配置..."
if sudo nginx -t; then
    echo "✓ 配置测试通过"
    echo ""
    echo "重载 Nginx..."
    sudo systemctl reload nginx
    echo "✓ Nginx 已重载"
    echo ""
    echo "测试 API 端点..."
    sleep 2
    curl -s https://deepinvestoragent.gravitechinnovations.com/api/health || echo "如果失败，请检查后端服务是否运行"
else
    echo "✗ 配置测试失败，请检查配置"
    echo "恢复备份..."
    sudo cp "${NGINX_CONF}.backup."* "$NGINX_CONF" 2>/dev/null || true
    exit 1
fi

echo ""
echo "=========================================="
echo "修复完成！"
echo "=========================================="

