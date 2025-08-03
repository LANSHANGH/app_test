# Dockerfile

# 步骤1: 选择一个包含Python的官方基础镜像
# 我们选择一个基于Debian (Bookworm)的稳定版本
FROM python:3.11-slim-bookworm

# 步骤2: 安装系统级依赖
# 在这里安装Ghostscript和任何其他你需要的工具
RUN apt-get update && apt-get install -y ghostscript && \
    # 清理apt缓存以减小镜像大小
    rm -rf /var/lib/apt/lists/*

# 步骤3: 设置工作目录
WORKDIR /app

# 步骤4: 复制依赖定义文件
COPY requirements.txt .

# 步骤5: 安装Python依赖
# 我们在这里也升级pip
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# 步骤6: 复制你所有的项目代码到镜像中
COPY . .

# 步骤7: 编译你的核心逻辑并清理源代码
# 这一步和之前在render.yaml里的一样
RUN python setup.py build_ext --inplace && rm secure_core.py

# 步骤8: 暴露端口 (Render会自动使用)
# Gunicorn默认绑定到8000，但Render会处理端口映射
EXPOSE 10000

# 步骤9: 设置环境变量 (可选，但推荐)
# 这会告诉Gunicorn它在一个生产环境中
ENV PYTHONUNBUFFERED 1

# 步骤10: 定义容器启动时要执行的命令
# 和之前一样，但包含了--timeout参数
CMD ["gunicorn", "--timeout", "120", "--bind", "0.0.0.0:10000", "app:app"]
