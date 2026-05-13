# 智能聊天机器人 - 部署指南

## 环境要求

### 后端

- Python 3.10+
- CUDA 11.8+ (GPU推理)
- 8GB+ RAM (CPU推理) / 16GB+ VRAM (GPU推理)
- 50GB+ 磁盘空间 (模型文件)

### 微信小程序

- 微信开发者工具
- 微信小程序AppID

## 后端部署

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```env
# 安全密钥（生产环境务必修改）
SECRET_KEY=your-secret-key-here

# 数据库
DATABASE_URL=sqlite:///./chatbot.db
# 或使用 PostgreSQL:
# DATABASE_URL=postgresql+asyncpg://user:password@localhost/chatbot

# Redis（可选，用于缓存和限流）
REDIS_URL=redis://localhost:6379/0

# Transformer 模型
MODEL_NAME=Qwen/Qwen-1_8B-Chat
MODEL_CACHE_DIR=./model_cache
MAX_CONTEXT_LENGTH=2048
MAX_HISTORY_TURNS=10

# 微信小程序
WX_APPID=your-wechat-appid
WX_SECRET=your-wechat-secret

# 日志
LOG_LEVEL=INFO
LOG_FILE=./logs/app.log
```

### 3. 下载模型

首次启动会自动下载模型，也可手动下载：

```bash
python -c "from transformers import AutoTokenizer, AutoModelForCausalLM; AutoTokenizer.from_pretrained('Qwen/Qwen-1_8B-Chat', cache_dir='./model_cache', trust_remote_code=True); AutoModelForCausalLM.from_pretrained('Qwen/Qwen-1_8B-Chat', cache_dir='./model_cache', trust_remote_code=True)"
```

### 4. 启动服务

开发环境：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

生产环境：

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 5. 使用 Docker 部署

创建 `Dockerfile`：

```dockerfile
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

构建并运行：

```bash
docker build -t chatbot-backend .
docker run -d -p 8000:8000 -v ./model_cache:/app/model_cache -v ./logs:/app/logs --env-file .env chatbot-backend
```

### 6. 使用 Docker Compose

```yaml
version: '3.8'
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./model_cache:/app/model_cache
      - ./logs:/app/logs
    env_file:
      - .env
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - backend
```

## Nginx 反向代理配置

```nginx
server {
    listen 443 ssl http2;
    server_name your-api-domain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # 超时设置
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }
}
```

## 微信小程序部署

### 1. 配置项目

1. 打开微信开发者工具
2. 导入 `miniprogram` 目录
3. 在 `project.config.json` 中填入你的 AppID
4. 修改 `app.js` 中的 `baseUrl` 为你的后端API地址

### 2. 准备图标资源

在 `miniprogram/assets/icons/` 目录下放置以下图标：

- `bot-avatar.png` - 机器人头像
- `user-avatar.png` - 默认用户头像
- `chat.png` / `chat-active.png` - 对话Tab图标
- `history.png` / `history-active.png` - 历史Tab图标
- `user.png` / `user-active.png` - 我的Tab图标

### 3. 配置服务器域名

在微信公众平台 → 开发管理 → 开发设置中，添加以下域名：

- request合法域名: `https://your-api-domain.com`
- socket合法域名: `wss://your-api-domain.com`
- uploadFile合法域名: `https://your-api-domain.com`
- downloadFile合法域名: `https://your-api-domain.com`

### 4. 上传与发布

1. 在微信开发者工具中点击"上传"
2. 填写版本号和备注
3. 在微信公众平台提交审核
4. 审核通过后发布

## 数据备份

### 自动备份脚本

```bash
#!/bin/bash
BACKUP_DIR="/backups/chatbot"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# 备份数据库
cp /app/chatbot.db "$BACKUP_DIR/chatbot_$DATE.db"

# 保留最近7天的备份
find $BACKUP_DIR -name "chatbot_*.db" -mtime +7 -delete

echo "Backup completed: chatbot_$DATE.db"
```

设置定时任务：

```bash
crontab -e
# 每天凌晨3点备份
0 3 * * * /path/to/backup.sh
```

## 性能优化

### GPU 加速

- 确保安装了对应版本的 CUDA 和 cuDNN
- 使用 `torch.cuda.is_available()` 验证GPU可用性
- 模型自动使用 float16 精度以节省显存

### 模型优化

- 使用 INT8/INT4 量化减小模型体积
- 使用 vLLM 或 TGI 作为推理后端提升吞吐量
- 考虑使用更小的模型（如 Qwen-1\_8B）降低延迟

### 缓存策略

- 启用 Redis 缓存热门对话
- 使用 CDN 加速静态资源
- 配置 Nginx 缓存 API 响应

## 监控与日志

### 日志查看

```bash
# 实时查看日志
tail -f logs/app.log

# 搜索错误日志
grep "ERROR" logs/app.log
```

### 健康检查

```bash
curl http://localhost:8000/health
```

## 安全注意事项

1. 生产环境必须修改 `SECRET_KEY`
2. 启用 HTTPS
3. 定期更新依赖包
4. 配置防火墙规则
5. 启用数据库访问控制
6. 定期审查日志中的异常请求

