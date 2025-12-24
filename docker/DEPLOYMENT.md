# 生产环境部署指南

本文档说明如何将 Deep Investor Agent 部署到生产环境，使用 Nginx 作为反向代理，并映射到外网域名 `https://deepinvestoragent.gravitechinnovations.com/documentation`。

## 前置要求

1. **服务器要求**
   - Ubuntu 20.04+ 或 CentOS 7+ 或类似 Linux 发行版
   - 至少 4GB RAM
   - 至少 20GB 磁盘空间
   - Docker 20.10+ 和 Docker Compose 1.29+

2. **域名和 SSL 证书**
   - 已配置域名 `deepinvestoragent.gravitechinnovations.com` 指向服务器 IP
   - SSL 证书文件（Let's Encrypt 或其他 CA 颁发的证书）

3. **API 密钥配置**
   - 已准备好所有必要的 API 密钥（见 `.env.example`）

## 部署步骤

### 1. 准备服务器

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装 Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 将当前用户添加到 docker 组（可选，避免每次使用 sudo）
sudo usermod -aG docker $USER
```

### 2. 克隆项目

```bash
cd /opt  # 或其他合适的目录
git clone <your-repo-url> deep-investor-agent
cd deep-investor-agent
```

### 3. 配置环境变量

```bash
# 复制环境变量示例文件
cp .env.example .env

# 编辑 .env 文件，填入所有必要的 API 密钥
nano .env
```

**重要配置项：**
- `OPENAI_API_KEY` 或其他 LLM API 密钥（至少配置一个）
- `FINANCIAL_DATASETS_API_KEY`（美股数据）
- `DEEPALPHA_API_KEY`（A股/港股数据）

### 4. 配置 SSL 证书

#### 方式一：使用自动化脚本（推荐）

如果遇到 80 端口被占用的问题，可以使用提供的自动化脚本：

```bash
cd docker
chmod +x setup-ssl.sh
sudo ./setup-ssl.sh
```

脚本会自动检测端口占用情况，并提供多种获取证书的方式。

#### 方式二：手动配置 Let's Encrypt

**如果 80 端口未被占用：**

```bash
# 安装 Certbot
sudo apt install certbot

# 获取证书
sudo certbot certonly --standalone -d deepinvestoragent.gravitechinnovations.com

# 复制证书到项目目录
sudo mkdir -p docker/nginx/ssl
sudo cp /etc/letsencrypt/live/deepinvestoragent.gravitechinnovations.com/fullchain.pem docker/nginx/ssl/
sudo cp /etc/letsencrypt/live/deepinvestoragent.gravitechinnovations.com/privkey.pem docker/nginx/ssl/
sudo chmod 644 docker/nginx/ssl/fullchain.pem
sudo chmod 600 docker/nginx/ssl/privkey.pem
```

**如果 80 端口被占用（如已有 Nginx 运行）：**

**选项 A: 使用 webroot 模式（推荐）**

```bash
# 创建 webroot 目录
sudo mkdir -p /var/www/certbot

# 获取证书（不需要停止 Nginx）
sudo certbot certonly --webroot \
    -w /var/www/certbot \
    -d deepinvestoragent.gravitechinnovations.com \
    --email your-email@example.com \
    --agree-tos

# 复制证书到项目目录
sudo mkdir -p docker/nginx/ssl
sudo cp /etc/letsencrypt/live/deepinvestoragent.gravitechinnovations.com/fullchain.pem docker/nginx/ssl/
sudo cp /etc/letsencrypt/live/deepinvestoragent.gravitechinnovations.com/privkey.pem docker/nginx/ssl/
sudo chmod 644 docker/nginx/ssl/fullchain.pem
sudo chmod 600 docker/nginx/ssl/privkey.pem
```

**选项 B: 临时停止服务后使用 standalone 模式**

```bash
# 停止占用 80 端口的服务（如 Nginx）
sudo systemctl stop nginx

# 获取证书
sudo certbot certonly --standalone -d deepinvestoragent.gravitechinnovations.com

# 重启服务
sudo systemctl start nginx

# 复制证书到项目目录
sudo mkdir -p docker/nginx/ssl
sudo cp /etc/letsencrypt/live/deepinvestoragent.gravitechinnovations.com/fullchain.pem docker/nginx/ssl/
sudo cp /etc/letsencrypt/live/deepinvestoragent.gravitechinnovations.com/privkey.pem docker/nginx/ssl/
sudo chmod 644 docker/nginx/ssl/fullchain.pem
sudo chmod 600 docker/nginx/ssl/privkey.pem
```

**选项 C: 使用 DNS 验证（不需要占用端口）**

```bash
# 使用 DNS 验证模式
sudo certbot certonly --manual \
    --preferred-challenges dns \
    -d deepinvestoragent.gravitechinnovations.com \
    --email your-email@example.com \
    --agree-tos

# 按照提示在 DNS 提供商处添加 TXT 记录，然后继续

# 复制证书到项目目录
sudo mkdir -p docker/nginx/ssl
sudo cp /etc/letsencrypt/live/deepinvestoragent.gravitechinnovations.com/fullchain.pem docker/nginx/ssl/
sudo cp /etc/letsencrypt/live/deepinvestoragent.gravitechinnovations.com/privkey.pem docker/nginx/ssl/
sudo chmod 644 docker/nginx/ssl/fullchain.pem
sudo chmod 600 docker/nginx/ssl/privkey.pem
```

#### 方式二：使用现有证书

```bash
# 将证书文件复制到项目目录
mkdir -p docker/nginx/ssl
cp /path/to/your/fullchain.pem docker/nginx/ssl/
cp /path/to/your/privkey.pem docker/nginx/ssl/
chmod 644 docker/nginx/ssl/fullchain.pem
chmod 600 docker/nginx/ssl/privkey.pem
```

### 5. 更新后端 CORS 配置

编辑 `app/backend/main.py`，更新 CORS 配置以允许生产域名：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://deepinvestoragent.gravitechinnovations.com",  # 添加生产域名
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 6. 部署应用

```bash
cd docker

# 给部署脚本添加执行权限
chmod +x deploy.sh

# 运行部署脚本
./deploy.sh
```

或者手动部署：

```bash
cd docker

# 停止现有容器（如果有）
docker-compose -f docker-compose.prod.yml down

# 构建镜像
docker-compose -f docker-compose.prod.yml build

# 启动服务
docker-compose -f docker-compose.prod.yml up -d

# 查看日志
docker-compose -f docker-compose.prod.yml logs -f
```

### 7. 验证部署

1. **检查容器状态**
   ```bash
   docker-compose -f docker-compose.prod.yml ps
   ```

2. **访问应用**
   - 前端：https://deepinvestoragent.gravitechinnovations.com
   - API 文档：https://deepinvestoragent.gravitechinnovations.com/documentation
   - API 端点：https://deepinvestoragent.gravitechinnovations.com/api

3. **检查健康状态**
   ```bash
   curl https://deepinvestoragent.gravitechinnovations.com/api/health
   ```

## 服务管理

### 查看日志

```bash
# 查看所有服务日志
docker-compose -f docker-compose.prod.yml logs -f

# 查看特定服务日志
docker-compose -f docker-compose.prod.yml logs -f backend
docker-compose -f docker-compose.prod.yml logs -f frontend
docker-compose -f docker-compose.prod.yml logs -f nginx
```

### 重启服务

```bash
# 重启所有服务
docker-compose -f docker-compose.prod.yml restart

# 重启特定服务
docker-compose -f docker-compose.prod.yml restart backend
```

### 停止服务

```bash
docker-compose -f docker-compose.prod.yml down
```

### 更新应用

```bash
cd docker

# 拉取最新代码
cd ..
git pull

# 重新构建并启动
cd docker
docker-compose -f docker-compose.prod.yml up -d --build
```

## SSL 证书自动续期（Let's Encrypt）

如果使用 Let's Encrypt，证书每 90 天需要续期。可以设置定时任务：

```bash
# 编辑 crontab
sudo crontab -e

# 添加以下行（每月 1 号凌晨 3 点检查并续期）
0 3 1 * * certbot renew --quiet --deploy-hook "cd /opt/deep-investor-agent/docker && docker-compose -f docker-compose.prod.yml restart nginx"
```

## 故障排查

### 1. 容器无法启动

```bash
# 查看详细日志
docker-compose -f docker-compose.prod.yml logs

# 检查容器状态
docker-compose -f docker-compose.prod.yml ps -a
```

### 2. SSL 证书问题

- 确保证书文件路径正确
- 检查证书文件权限
- 验证域名 DNS 解析是否正确

### 3. API 连接失败

- 检查后端服务是否正常运行：`docker-compose -f docker-compose.prod.yml ps backend`
- 检查后端日志：`docker-compose -f docker-compose.prod.yml logs backend`
- 验证 CORS 配置是否正确

### 4. 前端无法加载

- 检查前端容器是否运行：`docker-compose -f docker-compose.prod.yml ps frontend`
- 检查 Nginx 配置是否正确
- 查看浏览器控制台错误信息

## 性能优化

### 1. 调整工作进程数

编辑 `docker/Dockerfile.backend`，根据服务器 CPU 核心数调整 workers：

```dockerfile
CMD ["poetry", "run", "uvicorn", "app.backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 2. 启用 Nginx 缓存

已在配置中启用静态资源缓存，可根据需要调整缓存时间。

### 3. 数据库优化

如果使用 SQLite，考虑迁移到 PostgreSQL 或 MySQL 以获得更好的性能。

## 安全建议

1. **防火墙配置**
   ```bash
   # 只开放必要端口
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```

2. **定期更新**
   - 定期更新系统包
   - 定期更新 Docker 镜像
   - 定期更新应用代码

3. **备份**
   - 定期备份 `.env` 文件
   - 定期备份数据库文件（如果使用 SQLite）
   - 定期备份 SSL 证书

4. **监控**
   - 设置日志监控
   - 设置服务健康检查
   - 设置磁盘空间监控

## 架构说明

```
Internet
   |
   v
Nginx (443/80)
   |
   +---> Frontend (Vue3/React)
   |
   +---> Backend API (/api/*)
   |      |
   |      v
   |    FastAPI (8000)
   |
   +---> Documentation (/documentation)
         |
         v
       FastAPI Docs
```

## 联系支持

如遇到问题，请：
1. 查看日志文件
2. 检查本文档的故障排查部分
3. 提交 Issue 到项目仓库

