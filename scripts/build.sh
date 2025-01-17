#!/bin/bash

# 设置变量
IMAGE_NAME="symlink"
VERSION=$(git describe --tags --always --dirty)
PLATFORMS="linux/amd64,linux/arm64"

# 启用 buildx
docker buildx create --use

# 构建并推送多架构镜像
echo "构建版本: $VERSION"
docker buildx build \
    --platform $PLATFORMS \
    --tag $IMAGE_NAME:latest \
    --tag $IMAGE_NAME:$VERSION \
    --push \
    . 