# Dockerfile (自检加强版)

# 1. 基础镜像
FROM python:3.11-slim-bookworm

# 2. 安装系统依赖
# 我们把验证步骤也加在这里
RUN apt-get update && \
    apt-get install -y ghostscript build-essential && \
    rm -rf /var/lib/apt/lists/* && \
    # 【验证步骤1】: 确认ghostscript的可执行文件(gs)是否存在并且可以被找到
    which gs && \
    # 【验证步骤2】: 直接运行gs，看它是否能打印出版本号
    gs --version

# 3. 明确设置PATH (保持不变)
ENV PATH /usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH

# 4. 工作目录
WORKDIR /app

# 5. 安装Python依赖
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# 6. 复制并编译代码
COPY . .
RUN python setup.py build_ext --inplace && rm secure_core.py

# 7. 暴露端口
EXPOSE 10000

# 8. 启动命令
CMD ["gunicorn", "--timeout", "0", "--bind", "0.0.0.0:10000", "app:app"]
