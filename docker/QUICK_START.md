# 生产环境部署快速参考

## 一键部署命令

```bash
# 1. 进入 docker 目录
cd docker

# 2. 运行部署脚本
chmod +x deploy.sh
./deploy.sh
```

## 手动部署步骤

### 1. 准备 SSL 证书

**推荐：使用自动化脚本（自动处理端口占用问题）**

```bash
cd docker
chmod +x setup-ssl.sh
sudo ./setup-ssl.sh
```

**或者手动配置：**

```bash
# 如果 80 端口未被占用
sudo certbot certonly --standalone -d deepinvestoragent.gravitechinnovations.com

# 如果 80 端口被占用，使用 webroot 模式
sudo mkdir -p /var/www/certbot
sudo certbot certonly --webroot -w /var/www/certbot -d deepinvestoragent.gravitechinnovations.com

# 复制证书
sudo mkdir -p docker/nginx/ssl
sudo cp /etc/letsencrypt/live/deepinvestoragent.gravitechinnovations.com/fullchain.pem docker/nginx/ssl/
sudo cp /etc/letsencrypt/live/deepinvestoragent.gravitechinnovations.com/privkey.pem docker/nginx/ssl/
sudo chmod 644 docker/nginx/ssl/fullchain.pem
sudo chmod 600 docker/nginx/ssl/privkey.pem
```

### 2. 配置环境变量

```bash
# 在项目根目录创建 .env 文件
cp .env.example .env
nano .env  # 填入所有必要的 API 密钥
```

### 3. 部署

```bash
cd docker
docker-compose -f docker-compose.prod.yml up -d --build
```

## 常用命令

```bash
# 查看服务状态
docker-compose -f docker-compose.prod.yml ps

# 查看日志
docker-compose -f docker-compose.prod.yml logs -f

# 重启服务
docker-compose -f docker-compose.prod.yml restart

# 停止服务
docker-compose -f docker-compose.prod.yml down

# 更新应用
git pull && docker-compose -f docker-compose.prod.yml up -d --build
```

## 访问地址

- 前端: https://deepinvestoragent.gravitechinnovations.com
- API 文档: https://deepinvestoragent.gravitechinnovations.com/documentation
- API: https://deepinvestoragent.gravitechinnovations.com/api

## 故障排查

```bash
# 检查容器日志
docker-compose -f docker-compose.prod.yml logs backend
docker-compose -f docker-compose.prod.yml logs frontend
docker-compose -f docker-compose.prod.yml logs nginx

# 检查容器状态
docker-compose -f docker-compose.prod.yml ps

# 重启特定服务
docker-compose -f docker-compose.prod.yml restart backend
```

详细部署文档请参考 [DEPLOYMENT.md](DEPLOYMENT.md)

