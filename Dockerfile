# Dockerfile

# 步骤1: 选择一个包含Python的官方基础镜像
FROM python:3.11-slim-bookworm

# 步骤2: 安装系统级依赖
# 【重要修改】: 在这里同时安装ghostscript和编译工具链
RUN apt-get update && apt-get install -y ghostscript build-essential && \
    # 清理apt缓存以减小镜像大小
    rm -rf /var/lib/apt/lists/*

# 步骤3: 设置工作目录
WORKDIR /app

# 步骤4: 复制并安装Python依赖
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# 步骤5: 复制所有项目代码到镜像中
COPY . .

# 步骤6: 【构建逻辑】编译核心代码并清理
RUN python setup.py build_ext --inplace && rm secure_core.py

# 步骤7: 暴露端口
EXPOSE 10000

# 步骤8: 设置环境变量
ENV PYTHONUNBUFFERED 1

# 步骤9: 定义容器启动时要执行的命令
CMD ["gunicorn", "--timeout", "120", "--bind", "0.0.0.0:10000", "app:app"]
