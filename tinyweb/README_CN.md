# TinyWeb 安装配置启动文档

TinyWeb 是基于 Flask 的金融预测 Web 应用，集成了 Kronos 时间序列预测模型。

## 环境要求

- Python 3.11+
- 操作系统：Linux、macOS 或 Windows
- 内存：建议 8GB 以上（如果使用 GPU 预测）
- 磁盘空间：至少 2GB 可用空间

## 安装步骤

### 1. 克隆项目

```bash
# 如果从 Git 仓库克隆
git clone <repository-url>
cd Kronos/tinyweb

# 或者直接进入 tinyweb 目录
cd /path/to/Kronos/tinyweb
```

### 2. 创建 Python 虚拟环境

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
# Linux/macOS:
source venv/bin/activate
# Windows:
# venv\Scripts\activate
```

### 3. 安装依赖包

```bash
# 确保虚拟环境已激活
pip install --upgrade pip

# 安装项目依赖
pip install -r requirements.txt
```

## 配置说明

### 1. 环境配置文件

复制配置模板并创建 `.env` 文件：

```bash
cp config.env.example .env
```

编辑 `.env` 文件，配置以下参数：

```bash
# Kronos 模型配置
KRONOS_MODEL_KEY=kronos-base          # 可选：kronos-mini, kronos-small, kronos-base
KRONOS_MODEL_DEVICE=cpu               # 设备：cpu, cuda, mps

# Flask 配置
SECRET_KEY=your-secret-key-here       # Flask 密钥（可选，自动生成）

# 数据目录配置
DATA_DIR=./data                       # 数据存储目录

# 文件上传限制
MAX_UPLOAD_FILES=3                    # 每用户最大上传文件数
MAX_RESULT_FILES=3                    # 每用户最大结果文件数

# 管理员配置
ADMIN_WALLET_ADDRESS=0x...            # 管理员钱包地址
```

### 2. 创建必要目录

```bash
# 创建数据目录
mkdir -p data

# 确保有写入权限
chmod 755 data
```

### 3. 模型配置

TinyWeb 支持三种 Kronos 模型：

- **kronos-mini**: 4.1M 参数，轻量级模型，预测速度快
- **kronos-small**: 24.7M 参数，平衡性能和速度
- **kronos-base**: 102.3M 参数，基础模型，提供更好的预测质量

首次启动时，应用会自动从 HuggingFace 下载模型文件。

## 启动应用

### 方法一：使用启动脚本（推荐）

```bash
# 确保虚拟环境已激活
chmod +x start.sh
./start.sh
```

### 方法二：手动启动

```bash
# 确保虚拟环境已激活
python3 app.py
```

### 方法三：开发模式

```bash
# 开发模式，启用调试和热重载
export FLASK_ENV=development
python3 app.py
```

## 访问应用

启动成功后，访问以下地址：

- Web 界面：http://localhost:7070
- API 文档：http://localhost:7070 （应用内嵌）

## 使用说明

### 1. 数据上传

支持的数据格式：
- CSV 文件（.csv）
- Feather 文件（.feather）

数据文件必须包含以下列：
- `open`: 开盘价
- `high`: 最高价
- `low`: 最低价
- `close`: 收盘价

可选列：
- `volume`: 成交量
- `timestamps`/`timestamp`/`date`: 时间戳

### 2. 预测功能

- **历史数据点数**: 默认使用 400 个历史数据点
- **预测数据点数**: 默认预测 120 个未来数据点
- **质量参数**:
  - Temperature: 控制预测随机性（默认 1.0）
  - Top P: 核采样参数（默认 0.9）
  - Sample Count: 采样次数（默认 1）

### 3. 钱包认证

应用使用钱包地址进行用户认证：
- 首次访问需要连接钱包
- 每个用户有独立的数据存储空间
- 管理员钱包地址配置在 `.env` 文件中

## 生产环境部署

### 1. 使用 Gunicorn

```bash
# 安装 Gunicorn
pip install gunicorn

# 启动应用
gunicorn -w 4 -b 0.0.0.0:7070 app:app
```

### 2. 使用 Docker

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY . .

RUN python3 -m venv venv
ENV PATH="/app/venv/bin:$PATH"

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

EXPOSE 7070

CMD ["python", "app.py"]
```

构建和运行：

```bash
docker build -t tinyweb .
docker run -p 7070:7070 -v $(pwd)/data:/app/data tinyweb
```

### 3. Nginx 反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:7070;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

## API 端点

主要 API 端点：

- `GET /`: 主页
- `GET /api/data-files`: 获取数据文件列表
- `POST /api/upload-data`: 上传数据文件
- `POST /api/load-data`: 加载数据文件
- `POST /api/predict`: 执行预测
- `POST /api/only-predict`: 仅预测，无分析
- `GET /api/available-models`: 获取可用模型列表
- `GET /api/model-status`: 获取模型状态
- `POST /api/load-model`: 加载模型（管理员）
- `GET /api/download/<file_path>`: 下载文件

## 许可证

请参考项目根目录的 LICENSE 文件。
