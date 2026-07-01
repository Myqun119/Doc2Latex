FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖（pix2tex 需要）
RUN apt-get update && \
    apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY app/ /app/app/
COPY storage/ /app/storage/

# 创建存储目录
RUN mkdir -p /app/storage/in /app/storage/out

# 启动服务
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]