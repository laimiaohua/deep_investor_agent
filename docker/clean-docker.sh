#!/bin/bash

# Docker 清理脚本
# 用于清理构建缓存和未使用的资源

echo "=========================================="
echo "Docker 清理脚本"
echo "=========================================="
echo ""

# 停止所有相关容器
echo "停止相关容器..."
docker stop deep-investor-agent-backend deep-investor-agent-frontend 2>/dev/null || true

# 删除相关容器
echo "删除相关容器..."
docker rm deep-investor-agent-backend deep-investor-agent-frontend 2>/dev/null || true

# 删除相关镜像
echo "删除相关镜像..."
docker rmi deep-investor-agent-backend:latest deep-investor-agent-frontend:latest 2>/dev/null || true

# 清理构建缓存
echo "清理构建缓存..."
docker builder prune -af

# 清理未使用的镜像
echo "清理未使用的镜像..."
docker image prune -af

# 清理未使用的卷
echo "清理未使用的卷..."
docker volume prune -f

# 显示清理后的状态
echo ""
echo "=========================================="
echo "清理完成！"
echo "=========================================="
echo ""
echo "Docker 系统信息:"
docker system df
echo ""
echo "现在可以重新运行部署脚本:"
echo "  ./deploy-no-nginx.sh"
echo ""

