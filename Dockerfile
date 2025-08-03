# Dockerfile

# 1. 基础镜像
FROM python:3.11-slim-bookworm

# 2. 安装系统依赖 (包括Ghostscript)
RUN apt-get update && apt-get install -y ghostscript && rm -rf /var/lib/apt/lists/*

# 3. 设置工作目录
WORKDIR /app

# 4. 复制并安装Python依赖
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# 5. 复制所有项目代码
COPY . .

# 6. 【构建逻辑】编译核心代码并清理
RUN python setup.py build_ext --inplace && rm secure_core.py

# 7. 暴露端口
EXPOSE 10000

# 8. 【启动逻辑】定义启动命令，并包含超时设置
CMD ["gunicorn", "--timeout", "120", "--bind", "0.0.0.0:10000", "app:app"]
