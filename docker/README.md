# Docker 部署说明（已精简）

本目录仅保留生产部署所需的配置和脚本，去掉了旧版单容器/命令行运行的遗留文件，避免混淆。

## 可用的 Compose 文件
- `docker-compose.prod.yml`：内置 Nginx 的标准生产部署（推荐，80/443 直接暴露）
- `docker-compose.prod-no-nginx.yml`：仅启动前后端容器，适配已有外部 Nginx 代理（端口 8000/8080）

## 配套脚本
- `deploy.sh`：使用 `docker-compose.prod.yml` 一键部署，含 SSL 检查
- `deploy-no-nginx.sh`：使用 `docker-compose.prod-no-nginx.yml` 部署，配合外部 Nginx
- `setup-ssl.sh`：获取/更新证书（自动处理 80 端口占用场景）
- `setup-nginx.sh` / `fix-nginx-config.sh`：帮助在服务器侧检查或修复 Nginx 配置
- `clean-docker.sh`：清理相关容器/镜像/缓存
- 辅助检查脚本：`check-ports.sh`、`check-existing-nginx.sh`、`check-dns.sh`

## 典型流程
1) 创建 `.env`（项目根目录）：`cp .env.example .env` 并填好密钥  
2) 放置证书（如有）：`docker/nginx/ssl/fullchain.pem` 与 `privkey.pem`  
3) 任选其一：
   - 使用内置 Nginx：`cd docker && ./deploy.sh`
   - 使用外部 Nginx：`cd docker && ./deploy-no-nginx.sh`，再按 `SETUP_EXTERNAL_NGINX.md` 配置反向代理

## 目录精简说明
- 旧版单容器/命令行运行相关文件已移除：`docker-compose.yml`、`Dockerfile`（单容器版）、`run.sh`、`run.bat`、`docker-compose.prod-alt.yml`。
- 当前仅支持前后端分离的生产部署路径，如需本地开发请参考仓库根目录的 `README.md`（前后端各自启动）。

如需更多细节，参考同目录下的 `DEPLOYMENT.md`、`QUICK_START.md`、`SETUP_EXTERNAL_NGINX.md`。
