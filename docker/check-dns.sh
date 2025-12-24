#!/bin/bash

# DNS 配置检查脚本
# 用于验证域名 DNS 记录是否正确配置

DOMAIN="deepinvestoragent.gravitechinnovations.com"
EXPECTED_IP="43.155.22.226"

echo "=========================================="
echo "DNS 配置检查脚本"
echo "域名: ${DOMAIN}"
echo "期望 IP: ${EXPECTED_IP}"
echo "=========================================="
echo ""

# 检查 A 记录
echo "检查 A 记录 (IPv4)..."
A_RECORD=$(dig +short ${DOMAIN} A 2>/dev/null || nslookup ${DOMAIN} 2>/dev/null | grep -A 1 "Name:" | grep "Address:" | awk '{print $2}' || host ${DOMAIN} 2>/dev/null | grep "has address" | awk '{print $4}')

if [ -z "$A_RECORD" ]; then
    echo "❌ 错误: 无法解析 A 记录"
    echo "   域名 ${DOMAIN} 的 DNS 记录可能尚未生效或配置不正确"
    echo ""
    echo "请检查："
    echo "1. DNS 提供商处是否已添加 A 记录"
    echo "2. 主机记录是否为: deepinvestoragent"
    echo "3. 记录值是否为: ${EXPECTED_IP}"
    echo "4. 等待 DNS 传播（通常需要 5-30 分钟）"
else
    echo "✓ A 记录: ${A_RECORD}"
    if [ "$A_RECORD" = "$EXPECTED_IP" ]; then
        echo "✓ IP 地址匹配！"
    else
        echo "⚠ 警告: IP 地址不匹配"
        echo "   期望: ${EXPECTED_IP}"
        echo "   实际: ${A_RECORD}"
    fi
fi

echo ""

# 检查 AAAA 记录（IPv6，可选）
echo "检查 AAAA 记录 (IPv6)..."
AAAA_RECORD=$(dig +short ${DOMAIN} AAAA 2>/dev/null || nslookup -type=AAAA ${DOMAIN} 2>/dev/null | grep "AAAA" | awk '{print $NF}')

if [ -z "$AAAA_RECORD" ]; then
    echo "ℹ 未配置 IPv6 记录（这是正常的，如果不需要 IPv6）"
else
    echo "✓ AAAA 记录: ${AAAA_RECORD}"
fi

echo ""

# 检查域名是否可以访问
echo "检查 HTTP 连接..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 http://${DOMAIN} 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "000" ]; then
    echo "⚠ 无法连接到 ${DOMAIN} (HTTP)"
    echo "   可能原因："
    echo "   1. DNS 尚未生效"
    echo "   2. 服务器未运行 Web 服务"
    echo "   3. 防火墙阻止了连接"
else
    echo "✓ HTTP 响应码: ${HTTP_CODE}"
fi

echo ""

# 总结
if [ -n "$A_RECORD" ] && [ "$A_RECORD" = "$EXPECTED_IP" ]; then
    echo "=========================================="
    echo "✓ DNS 配置正确！"
    echo "=========================================="
    echo ""
    echo "现在可以运行 SSL 证书获取脚本:"
    echo "  cd docker && sudo ./setup-ssl.sh"
    echo ""
else
    echo "=========================================="
    echo "❌ DNS 配置需要检查"
    echo "=========================================="
    echo ""
    echo "请按照以下步骤操作："
    echo ""
    echo "1. 登录您的 DNS 提供商管理面板"
    echo "2. 找到域名 gravitechinnovations.com 的 DNS 设置"
    echo "3. 添加以下 A 记录："
    echo "   - 主机记录: deepinvestoragent"
    echo "   - 记录类型: A"
    echo "   - 记录值: ${EXPECTED_IP}"
    echo "   - TTL: 600 (或默认值)"
    echo ""
    echo "4. 保存设置后，等待 5-30 分钟让 DNS 生效"
    echo "5. 重新运行此脚本验证: ./check-dns.sh"
    echo ""
fi

