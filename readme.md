# Symlink 文件监控与软链接管理系统

## 项目简介
Symlink 是一个用于监控 Google Drive 和本地目录文件变化，自动生成软链接并通知 Emby 刷新媒体库的系统。它专为无桌面环境的 Linux 系统设计，支持 Docker 部署，提供 Web UI 界面进行管理。

## 主要功能
- 🔍 **文件监控**
  - Google Drive 文件变化监控
  - 本地目录实时监控
  - 支持多种视频文件格式
  - 增量扫描和缓存机制

- 🔗 **软链接管理**
  - 自动创建和维护软链接
  - 保持原始目录结构
  - 支持覆盖已存在的软链接
  - 批量处理能力

- 📺 **Emby 集成**
  - 自动通知 Emby 刷新媒体库
  - 支持批量刷新
  - 失败重试机制

- 🖥️ **Web 管理界面**
  - 实时监控状态展示
  - 配置管理
  - 文件浏览
  - 操作日志查看

## 快速开始

### 使用 Docker 部署（推荐）

1. **创建配置文件目录**
```bash
mkdir -p symlink/{config,data}
cd symlink
```

2. **下载示例配置文件**
```bash
# 下载配置文件
curl -o config/config.yaml https://raw.githubusercontent.com/gray777/symlink/main/config/config.yaml.example

# 编辑配置文件
vim config/config.yaml
```

3. **创建 docker-compose.yml**
```yaml
version: '3.8'

services:
  symlink:
    image: gray777/symlink:latest
    container_name: symlink
    volumes:
      # 配置文件
      - ./config:/app/config:ro
      # 数据目录
      - ./data:/app/data
      # 挂载点
      - ${MOUNT_POINT:-/media/mount}:/media/mount:shared
      # 软链接目标目录
      - ${TARGET_BASE:-/media/links}:/media/links
      # 日志目录
      - ${LOG_PATH:-/var/log/symlink}:/var/log/symlink
    environment:
      - MOUNT_POINT=/media/mount
      - TARGET_BASE=/media/links
      - LOG_PATH=/var/log/symlink
      - DATABASE_PATH=/app/data/database.db
      - TZ=Asia/Shanghai
    ports:
      - "8501:8501"  # Streamlit Web UI
      - "8000:8000"  # FastAPI
    restart: unless-stopped
    privileged: true  # 需要特权模式以支持软链接操作
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 5s

```

4. **启动服务**
```bash
docker-compose up -d
```

5. **访问服务**
- Web UI: http://localhost:8501
- API 文档: http://localhost:8000/docs

### 手动构建部署

如果您需要修改源码或自定义构建，可以采用手动构建的方式：

1. **克隆项目**
```bash
git clone https://github.com/gray777/symlink.git
cd symlink
```

2. **构建镜像**
```bash
docker build -t symlink:local .
```

3. **使用自构建镜像**
修改 docker-compose.yml 中的 image 为 `symlink:local`，然后按照上述步骤启动服务。

### 容器管理命令

```bash
# 查看容器日志
docker-compose logs -f

# 重启服务
docker-compose restart

# 停止服务
docker-compose down

# 更新镜像
docker-compose pull
docker-compose up -d
```

## 配置说明

### 环境变量配置
您可以通过以下方式自定义环境变量：

1. **直接修改 docker-compose.yml**
```yaml
environment:
  - MOUNT_POINT=/your/custom/mount/path
  - TARGET_BASE=/your/custom/target/path
  - LOG_PATH=/your/custom/log/path
  - DATABASE_PATH=/app/data/database.db
  - TZ=Asia/Shanghai
```

2. **使用 .env 文件**
```bash
# 创建 .env 文件
cat > .env << EOF
MOUNT_POINT=/your/custom/mount/path
TARGET_BASE=/your/custom/target/path
LOG_PATH=/your/custom/log/path
EOF
```

3. **命令行指定**
```bash
MOUNT_POINT=/custom/path docker-compose up -d
```

### 必要的环境变量
- `MOUNT_POINT`: rclone 挂载点路径
- `TARGET_BASE`: 软链接目标目录
- `LOG_PATH`: 日志目录
- `DATABASE_PATH`: 数据库文件路径

### 配置文件 (config.yaml)
```yaml
# Google Drive 配置
google_drive:
  folder_id: ""  # Google Drive 文件夹 ID
  api_key: ""    # API 密钥
  api_call_interval: 3600  # 调用间隔（秒）

# 本地监控配置
local_monitor:
  mount_point: "/media/mount"  # 挂载点路径
  polling_interval: 300  # 轮询间隔（秒）

# Emby 配置
emby:
  server_url: "http://localhost:8096"
  api_key: ""  # Emby API 密钥
```

## Google Drive 授权

由于项目运行在无桌面环境，提供两种授权方式：

1. **使用 rclone 配置**
   - 使用 rclone 完成 Google Drive 授权
   - 项目自动读取 rclone 配置文件

2. **手动授权**
   - 在本地完成 OAuth 授权流程
   - 将授权信息复制到服务器

## 目录结构
```
symlink/
├── config/             # 配置文件
├── src/               # 源代码
│   ├── core/          # 核心模块
│   └── gui.py         # Web UI
├── scripts/           # 脚本文件
├── templates/         # HTML 模板
└── docker-compose.yml # Docker 配置
```

## 健康检查

系统提供以下健康检查：
- Google Drive API 连接状态
- rclone 挂载点状态
- 数据库连接状态
- Emby 服务可用性
- 磁盘空间使用情况

## API 文档

访问 http://localhost:8000/docs 查看完整的 API 文档，主要接口：
- `/status`: 获取系统状态
- `/monitor/local/{action}`: 控制本地监控
- `/monitor/gdrive/{action}`: 控制 Google Drive 监控
- `/emby/refresh`: 刷新 Emby 媒体库

## 日志管理

- 日志位置: `/var/log/symlink/app.log`
- 日志级别: INFO（可在配置文件中调整）
- 自动日志轮转：保留最近 5 个日志文件

## 常见问题

1. **rclone 挂载失败**
   - 检查 rclone 配置文件权限
   - 确认 Google Drive API 授权是否有效

2. **软链接创建失败**
   - 检查目标目录权限
   - 确认源文件是否存在

3. **Emby 刷新失败**
   - 验证 Emby API 密钥
   - 检查 Emby 服务器连接状态

## 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 许可证

本项目采用 MIT 许可证