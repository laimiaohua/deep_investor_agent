# 使用外部 Nginx 作为反向代理的配置指南

本指南说明如何配置服务器上已有的 Nginx 来代理 Deep Investor Agent 应用。

## 前置条件

- 服务器上已安装并运行 Nginx
- 已获取 SSL 证书（Let's Encrypt 或其他）
- Docker 和 Docker Compose 已安装

## 部署步骤

### 步骤 1: 部署 Docker 服务（不包含 Nginx）

```bash
cd /root/gravitech_deep_investor_agent/docker

# 运行部署脚本
chmod +x deploy-no-nginx.sh
./deploy-no-nginx.sh
```

这将启动：
- 后端服务：端口 8000
- 前端服务：端口 8080

### 步骤 2: 检查服务是否正常运行

```bash
# 检查容器状态
docker compose -f docker-compose.prod-no-nginx.yml ps

# 测试后端 API
curl http://localhost:8000/health

# 测试前端（如果浏览器可以访问服务器）
curl http://localhost:8080
```

### 步骤 3: 配置外部 Nginx

#### 3.1 复制配置模板

```bash
cd /root/gravitech_deep_investor_agent/docker

# CentOS/RHEL/OpenCloudOS
sudo cp nginx-external.conf.example /etc/nginx/conf.d/deepinvestoragent.conf

# Debian/Ubuntu
sudo cp nginx-external.conf.example /etc/nginx/sites-available/deepinvestoragent.conf
sudo ln -s /etc/nginx/sites-available/deepinvestoragent.conf /etc/nginx/sites-enabled/
```

#### 3.2 编辑配置文件

```bash
# CentOS/RHEL/OpenCloudOS
sudo nano /etc/nginx/conf.d/deepinvestoragent.conf

# Debian/Ubuntu
sudo nano /etc/nginx/sites-available/deepinvestoragent.conf
```

**重要配置项检查：**

1. **SSL 证书路径**（如果使用 Let's Encrypt）：
   ```nginx
   ssl_certificate /etc/letsencrypt/live/deepinvestoragent.gravitechinnovations.com/fullchain.pem;
   ssl_certificate_key /etc/letsencrypt/live/deepinvestoragent.gravitechinnovations.com/privkey.pem;
   ```

2. **后端端口**（确认 Docker 容器映射的端口）：
   ```nginx
   upstream deep_investor_backend {
       server 127.0.0.1:8000;  # 确认端口号
   }
   ```

3. **前端端口**（确认 Docker 容器映射的端口）：
   ```nginx
   upstream deep_investor_frontend {
       server 127.0.0.1:8080;  # 确认端口号
   }
   ```

#### 3.3 测试 Nginx 配置

```bash
sudo nginx -t
```

如果测试通过，应该看到：
```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

#### 3.4 重载 Nginx

```bash
sudo systemctl reload nginx
# 或
sudo service nginx reload
```

### 步骤 4: 验证部署

1. **检查 Nginx 状态**：
   ```bash
   sudo systemctl status nginx
   ```

2. **检查端口监听**：
   ```bash
   sudo netstat -tulpn | grep -E ':(80|443) '
   # 或
   sudo ss -tulpn | grep -E ':(80|443) '
   ```

3. **测试访问**：
   - 前端：`https://deepinvestoragent.gravitechinnovations.com`
   - API 文档：`https://deepinvestoragent.gravitechinnovations.com/documentation`
   - API 端点：`https://deepinvestoragent.gravitechinnovations.com/api/health`

## 故障排查

### 问题 1: 502 Bad Gateway

**原因**：Nginx 无法连接到后端或前端服务

**解决方法**：
```bash
# 检查 Docker 容器是否运行
docker compose -f docker-compose.prod-no-nginx.yml ps

# 检查端口是否正确映射
docker compose -f docker-compose.prod-no-nginx.yml ps | grep -E '(8000|8080)'

# 测试本地连接
curl http://localhost:8000/health
curl http://localhost:8080

# 检查 Nginx 配置中的 upstream 端口是否正确
sudo grep -A 2 "upstream" /etc/nginx/conf.d/deepinvestoragent.conf
```

### 问题 2: SSL 证书错误

**原因**：证书路径不正确或证书不存在

**解决方法**：
```bash
# 检查证书文件是否存在
sudo ls -la /etc/letsencrypt/live/deepinvestoragent.gravitechinnovations.com/

# 如果证书不存在，重新获取
sudo certbot certonly --webroot -w /var/www/certbot -d deepinvestoragent.gravitechinnovations.com

# 更新 Nginx 配置中的证书路径
sudo nano /etc/nginx/conf.d/deepinvestoragent.conf
```

### 问题 3: 前端页面空白或 API 请求失败

**原因**：前端 API URL 配置不正确

**解决方法**：
1. 检查前端构建时的环境变量：
   ```bash
   # 查看 Dockerfile.frontend 中的 VITE_API_URL
   cat docker/Dockerfile.frontend | grep VITE_API_URL
   ```

2. 如果 API URL 不正确，重新构建前端：
   ```bash
   cd docker
   docker compose -f docker-compose.prod-no-nginx.yml build frontend
   docker compose -f docker-compose.prod-no-nginx.yml up -d frontend
   ```

### 问题 4: 端口冲突

**原因**：8000 或 8080 端口被其他服务占用

**解决方法**：
```bash
# 检查端口占用
sudo lsof -i :8000
sudo lsof -i :8080

# 如果被占用，修改 docker-compose.prod-no-nginx.yml 中的端口映射
# 然后更新 Nginx 配置中的 upstream 端口
```

## 服务管理

### 查看日志

```bash
# Docker 服务日志
cd /root/gravitech_deep_investor_agent/docker
docker compose -f docker-compose.prod-no-nginx.yml logs -f

# Nginx 日志
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### 重启服务

```bash
# 重启 Docker 服务
cd /root/gravitech_deep_investor_agent/docker
docker compose -f docker-compose.prod-no-nginx.yml restart

# 重启 Nginx
sudo systemctl restart nginx
```

### 更新应用

```bash
cd /root/gravitech_deep_investor_agent

# 拉取最新代码
git pull

# 重新构建并启动
cd docker
docker compose -f docker-compose.prod-no-nginx.yml up -d --build
```

## 多站点配置

如果您的服务器上运行多个项目（如 deepalpha 和 deepinvestoragent），确保：

1. **每个项目使用不同的域名**
2. **每个项目有独立的 Nginx 配置文件**
3. **Docker 容器使用不同的端口映射**

示例配置结构：
```
/etc/nginx/conf.d/
├── deepalpha.conf          # deepalpha 项目配置
└── deepinvestoragent.conf  # deepinvestoragent 项目配置
```

## 安全建议

1. **防火墙配置**：
   ```bash
   # 只开放必要端口
   sudo firewall-cmd --permanent --add-service=http
   sudo firewall-cmd --permanent --add-service=https
   sudo firewall-cmd --reload
   ```

2. **定期更新**：
   - 定期更新 Docker 镜像
   - 定期更新系统包
   - 定期更新 SSL 证书（Let's Encrypt 自动续期）

3. **监控**：
   - 设置日志监控
   - 设置服务健康检查
   - 设置磁盘空间监控

## 完成

配置完成后，您可以通过以下地址访问应用：

- **前端应用**: `https://deepinvestoragent.gravitechinnovations.com`
- **API 文档**: `https://deepinvestoragent.gravitechinnovations.com/documentation`
- **API 端点**: `https://deepinvestoragent.gravitechinnovations.com/api`

如有问题，请查看日志或参考故障排查部分。

