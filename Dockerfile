# Dockerfile

# 步骤1: 基础镜像
FROM python:3.11-slim-bookworm

# 步骤2: 安装系统依赖
RUN apt-get update && apt-get install -y ghostscript build-essential && \
    rm -rf /var/lib/apt/lists/*

# 【重要修改】: 明确设置PATH环境变量
# 这会确保Python的子进程能找到像gs (Ghostscript)这样的系统命令
ENV PATH /usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH

# 步骤3: 设置工作目录
WORKDIR /app

# 步骤4: 复制并安装Python依赖
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# 步骤5: 复制所有项目代码
COPY . .

# 步骤6: 编译核心代码并清理
RUN python setup.py build_ext --inplace && rm secure_core.py

# 步骤7: 暴露端口
EXPOSE 10000

# 步骤8: 设置环境变量
ENV PYTHONUNBUFFERED 1

# 步骤9: 定义启动命令
CMD ["gunicorn", "--timeout", "120", "--bind", "0.0.0.0:10000", "app:app"]
