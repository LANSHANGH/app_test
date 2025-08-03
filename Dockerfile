# Dockerfile

# 【重要修改】: 换用一个功能更完整的非slim基础镜像
FROM python:3.11-bookworm

# 步骤2: 安装系统依赖 (保持不变)
RUN apt-get update && \
    apt-get install -y ghostscript build-essential && \
    rm -rf /var/lib/apt/lists/*

# (自检步骤可以暂时保留，也可以移除)
RUN which gs && gs --version

# (PATH设置可以暂时保留，也可以移除，因为完整版镜像的PATH通常是正确的)
ENV PATH /usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH

# --- 后续所有步骤保持不变 ---
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python setup.py build_ext --inplace && rm secure_core.py
EXPOSE 10000
CMD ["gunicorn", "--timeout", "0", "--bind", "0.0.0.0:10000", "app:app"]
