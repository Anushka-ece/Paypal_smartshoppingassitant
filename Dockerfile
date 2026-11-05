FROM node:20-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libpq-dev \
        python3 \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt
ENV PATH="/opt/venv/bin:${PATH}"

COPY project_ver_1/backend ./project_ver_1/backend
COPY project_ver_1/frontend/package.json project_ver_1/frontend/package-lock.json ./project_ver_1/frontend/
WORKDIR /app/project_ver_1/frontend
RUN npm ci

COPY project_ver_1/frontend /app/project_ver_1/frontend
RUN npm run build

COPY scripts/start-render-demo.sh /app/scripts/start-render-demo.sh
RUN chmod +x /app/scripts/start-render-demo.sh

EXPOSE 10000
CMD ["/app/scripts/start-render-demo.sh"]
