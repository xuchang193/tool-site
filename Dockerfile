FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .

# 使用国内镜像 + 升级 pip + 延长超时时间
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --timeout=120 \
    --no-cache-dir -r requirements.txt && \
    pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

COPY . .

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]

