# Symlink 文件监控与软链接管理系统

## 项目概述
Symlink 是一个用于监控文件变化并生成软链接的系统，支持通过 Google Drive API 和本地目录监控文件变化。检测到文件变化后，系统会自动更新数据库、生成软链接，并通知 Emby 刷新媒体库。

## 功能模块
1. **Google Drive 监控 (`gdrive_api.py`)**  
   - 通过 Google Drive Activity API 监控指定文件夹的文件变化。
   - 定时调用 API，解析数据，对比数据库，更新文件信息，生成软链接并通知 Emby。

2. **本地目录监控 (`local_monitor.py`)**  
   - 使用 `watchdog` 库和轮询机制监控本地目录的文件变化。
   - 支持实时监控和轮询监控，优化措施包括增量扫描、缓存机制和并行处理。

3. **软链接管理 (`symlink_manager.py`)**  
   - 根据文件变化生成软链接。

4. **Emby 通知 (`emby_notifier.py`)**  
   - 通过 HTTP 请求通知 Emby 刷新媒体库。

5. **数据库管理 (`db_manager.py`)**  
   - 使用 SQLite 数据库记录文件目录结构，支持快照功能。

6. **快照生成 (`snapshot_generator.py`)**  
   - 根据数据库生成文件目录的快照，并生成 HTML 页面。

7. **图形操作界面 (`gui.py`)**  
   - 使用 Streamlit 构建图形操作界面，支持监控状态显示、配置管理、文件浏览和快照查看。

8. **配置管理 (`config_manager.py`)**
   - 统一管理所有配置项，支持 YAML 格式配置
   - 支持配置热重载和合法性验证

9. **日志管理 (`log_manager.py`)**
   - 统一的日志记录和管理系统
   - 支持日志分级、轮转和格式化
   - 提供系统运行状态监控指标

10. **任务队列 (`task_queue.py`)**
    - 管理文件处理任务，支持任务优先级
    - 提供失败任务重试机制
    - 支持批量处理和并发控制

11. **健康检查 (`health_checker.py`)**
    - 监控系统组件健康状态
    - 检查各项服务连接状态
    - 监控系统资源使用情况


## 使用方法
1. **配置环境**  
   - 安装依赖：`pip install -r requirements.txt`  
   - 配置 Google Drive API 密钥和 Emby 服务器地址。

2. **启动监控**  
   - 运行 `python main.py` 启动监控系统。

3. **使用图形界面**  
   - 运行 `streamlit run gui.py` 启动图形操作界面。

## Google Drive API 授权
由于项目运行在无桌面环境的 Linux 系统上，无法通过浏览器完成 OAuth 授权流程。以下是两种解决方案：
1. **参考 rclone 的异地授权方式**：
   - 在本地机器上完成 OAuth 授权流程，获取授权码。
   - 将授权码复制到服务器上，通过代码交换授权码获取访问令牌和刷新令牌。
2. **直接引用 rclone 的已授权配置文件**：
   - 解析 rclone 配置文件（`~/.config/rclone/rclone.conf`），提取 Google Drive 的访问令牌和刷新令牌。
   - 在代码中使用提取的令牌初始化 Google Drive API 客户端。

## 授权配置
- 如果使用 rclone 的配置文件，确保 rclone 已完成 Google Drive 的授权。
- 如果使用异地授权方式，请参考 [Google OAuth 文档](https://developers.google.com/identity/protocols/oauth2) 完成授权流程。

## 参考文档
- [Google Drive Activity API 官方文档](https://developers.google.cn/drive/activity/v2?hl=zh-cn)
- [MoviePilot 参考实现](https://github.com/jxxghp/MoviePilot)

## 部署方式

### Docker 部署（推荐）
1. **构建镜像**
```bash
docker build -t symlink:latest .
```

2. **运行容器**
```bash
docker run -d \
  --name symlink \
  --restart unless-stopped \
  -v /path/to/config:/app/config \
  -v /path/to/data:/app/data \
  -v /path/to/rclone:/root/.config/rclone \
  -e GOOGLE_DRIVE_FOLDER_ID=your_folder_id \
  -e EMBY_SERVER_URL=http://your_emby_server \
  -e EMBY_API_KEY=your_emby_api_key \
  symlink:latest
```

3. **环境变量说明**
- `GOOGLE_DRIVE_FOLDER_ID`: Google Drive 监控的文件夹 ID
- `EMBY_SERVER_URL`: Emby 服务器地址
- `EMBY_API_KEY`: Emby API 密钥
- `API_CALL_INTERVAL`: API 调用间隔时间（可选，默认 3600 秒）
- `POLLING_INTERVAL`: 本地目录轮询间隔时间（可选，默认 300 秒）

4. **挂载卷说明**
- `/app/config`: 配置文件目录
- `/app/data`: 数据库和日志文件目录
- `/root/.config/rclone`: rclone 配置文件目录

5. **健康检查**
容器内置了健康检查机制，会定期检查以下项目：
- Google Drive API 连接状态
- rclone 挂载点状态
- 数据库连接状态
- Emby 服务可用性

### 手动部署