#!/bin/bash

# SSL 证书设置脚本
# 用于解决端口占用问题并获取 SSL 证书
# 支持 Debian/Ubuntu 和 CentOS/RHEL 系统

set -e

DOMAIN="deepinvestoragent.gravitechinnovations.com"
CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"
PROJECT_SSL_DIR="$(dirname "$0")/nginx/ssl"

echo "=========================================="
echo "SSL 证书设置脚本"
echo "域名: ${DOMAIN}"
echo "=========================================="

# 检查 80 端口占用情况
echo "检查 80 端口占用情况..."
if lsof -i :80 &> /dev/null || netstat -tuln | grep -q ":80 " || ss -tuln | grep -q ":80 "; then
    echo "警告: 80 端口已被占用"
    echo ""
    echo "占用 80 端口的进程:"
    if command -v lsof &> /dev/null; then
        sudo lsof -i :80 || true
    elif command -v netstat &> /dev/null; then
        sudo netstat -tulpn | grep ":80 " || true
    elif command -v ss &> /dev/null; then
        sudo ss -tulpn | grep ":80 " || true
    fi
    echo ""
    
    # 检查是否是 Nginx
    if systemctl is-active --quiet nginx 2>/dev/null || pgrep nginx > /dev/null; then
        echo "检测到 Nginx 正在运行"
        echo ""
        echo "请选择获取证书的方式:"
        echo "1. 使用 webroot 模式（推荐，不需要停止 Nginx）"
        echo "2. 停止 Nginx 后使用 standalone 模式"
        echo "3. 使用 DNS 验证模式（不需要占用端口）"
        echo ""
        read -p "请选择 (1/2/3): " choice
        
        case $choice in
            1)
                echo "使用 webroot 模式获取证书..."
                # 确保 webroot 目录存在
                sudo mkdir -p /var/www/certbot
                
                # 检测系统类型并配置 Nginx（如果需要）
                # CentOS/RHEL 使用 /etc/nginx/conf.d/
                # Debian/Ubuntu 使用 /etc/nginx/sites-available/
                NGINX_CONF_DIR=""
                NGINX_CONF_FILE=""
                
                if [ -d "/etc/nginx/conf.d" ]; then
                    # CentOS/RHEL 系统
                    NGINX_CONF_DIR="/etc/nginx/conf.d"
                    NGINX_CONF_FILE="${NGINX_CONF_DIR}/certbot-temp.conf"
                elif [ -d "/etc/nginx/sites-available" ]; then
                    # Debian/Ubuntu 系统
                    NGINX_CONF_DIR="/etc/nginx/sites-available"
                    NGINX_CONF_FILE="${NGINX_CONF_DIR}/certbot-temp"
                fi
                
                # 如果检测到 Nginx 配置目录，尝试创建临时配置
                if [ -n "${NGINX_CONF_FILE}" ] && [ ! -f "${NGINX_CONF_FILE}" ]; then
                    echo "创建临时 Nginx 配置以支持证书验证..."
                    sudo tee "${NGINX_CONF_FILE}" > /dev/null <<EOF
server {
    listen 80;
    server_name ${DOMAIN};
    
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    
    location / {
        return 301 https://\$server_name\$request_uri;
    }
}
EOF
                    
                    # 如果是 Debian/Ubuntu，需要创建符号链接
                    if [ -d "/etc/nginx/sites-enabled" ]; then
                        sudo ln -sf "${NGINX_CONF_FILE}" /etc/nginx/sites-enabled/certbot-temp
                    fi
                    
                    # 测试并重载 Nginx
                    if sudo nginx -t 2>/dev/null; then
                        sudo systemctl reload nginx 2>/dev/null || sudo service nginx reload 2>/dev/null || true
                        echo "Nginx 配置已更新"
                    else
                        echo "警告: Nginx 配置测试失败，但继续尝试获取证书..."
                        echo "如果失败，请手动配置 Nginx 支持 /.well-known/acme-challenge/ 路径"
                    fi
                else
                    echo "提示: 如果证书获取失败，请确保 Nginx 已配置支持 /.well-known/acme-challenge/ 路径"
                    echo "      或者使用选项 2（停止 Nginx）或选项 3（DNS 验证）"
                fi
                
                echo ""
                echo "正在获取证书..."
                sudo certbot certonly --webroot \
                    -w /var/www/certbot \
                    -d ${DOMAIN} \
                    --email admin@gravitechinnovations.com \
                    --agree-tos \
                    --non-interactive
                
                # 清理临时配置（可选）
                if [ -n "${NGINX_CONF_FILE}" ] && [ -f "${NGINX_CONF_FILE}" ]; then
                    read -p "是否删除临时 Nginx 配置文件? (y/n) " -n 1 -r
                    echo
                    if [[ $REPLY =~ ^[Yy]$ ]]; then
                        sudo rm -f "${NGINX_CONF_FILE}"
                        if [ -L "/etc/nginx/sites-enabled/certbot-temp" ]; then
                            sudo rm -f /etc/nginx/sites-enabled/certbot-temp
                        fi
                        if sudo nginx -t 2>/dev/null; then
                            sudo systemctl reload nginx 2>/dev/null || sudo service nginx reload 2>/dev/null || true
                        fi
                        echo "临时配置文件已删除"
                    fi
                fi
                ;;
            2)
                echo "停止 Nginx..."
                sudo systemctl stop nginx 2>/dev/null || sudo service nginx stop 2>/dev/null || pkill nginx || true
                sleep 2
                
                echo "使用 standalone 模式获取证书..."
                sudo certbot certonly --standalone \
                    -d ${DOMAIN} \
                    --email admin@gravitechinnovations.com \
                    --agree-tos \
                    --non-interactive
                
                echo "重启 Nginx..."
                sudo systemctl start nginx 2>/dev/null || sudo service nginx start 2>/dev/null || true
                ;;
            3)
                echo "使用 DNS 验证模式..."
                echo "请按照 Certbot 的提示，在您的 DNS 提供商处添加 TXT 记录"
                sudo certbot certonly --manual \
                    --preferred-challenges dns \
                    -d ${DOMAIN} \
                    --email admin@gravitechinnovations.com \
                    --agree-tos
                ;;
            *)
                echo "无效选择，退出"
                exit 1
                ;;
        esac
    else
        echo "检测到其他进程占用 80 端口"
        echo "请先停止占用 80 端口的服务，然后重新运行此脚本"
        echo ""
        echo "或者使用 DNS 验证模式:"
        echo "sudo certbot certonly --manual --preferred-challenges dns -d ${DOMAIN}"
        exit 1
    fi
else
    echo "80 端口未被占用，使用 standalone 模式获取证书..."
    sudo certbot certonly --standalone \
        -d ${DOMAIN} \
        --email admin@gravitechinnovations.com \
        --agree-tos \
        --non-interactive
fi

# 检查证书是否成功获取
if [ ! -f "${CERT_DIR}/fullchain.pem" ] || [ ! -f "${CERT_DIR}/privkey.pem" ]; then
    echo "错误: 证书获取失败，请检查错误信息"
    exit 1
fi

# 复制证书到项目目录
echo ""
echo "复制证书到项目目录..."
mkdir -p "${PROJECT_SSL_DIR}"
sudo cp "${CERT_DIR}/fullchain.pem" "${PROJECT_SSL_DIR}/"
sudo cp "${CERT_DIR}/privkey.pem" "${PROJECT_SSL_DIR}/"
sudo chmod 644 "${PROJECT_SSL_DIR}/fullchain.pem"
sudo chmod 600 "${PROJECT_SSL_DIR}/privkey.pem"
sudo chown $USER:$USER "${PROJECT_SSL_DIR}/fullchain.pem" "${PROJECT_SSL_DIR}/privkey.pem" 2>/dev/null || true

echo ""
echo "=========================================="
echo "SSL 证书设置完成！"
echo "=========================================="
echo "证书位置:"
echo "  - ${PROJECT_SSL_DIR}/fullchain.pem"
echo "  - ${PROJECT_SSL_DIR}/privkey.pem"
echo ""
echo "现在可以运行部署脚本:"
echo "  cd docker && ./deploy.sh"
echo ""

