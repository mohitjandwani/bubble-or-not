# Stage 1 — build the SPA
FROM node:22-slim AS ui
WORKDIR /app/dashboard
COPY dashboard/package*.json ./
RUN npm ci
COPY dashboard/ ./
COPY data/fixtures/ /app/data/fixtures/
RUN cp /app/data/fixtures/*.json public/fixtures/ && npm run build

# Stage 2 — API + pipeline, serving the built SPA
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt asyncpg
COPY schema.py schema.sql ./
COPY agents/ agents/
COPY config/ config/
COPY data/ data/
COPY scripts/ scripts/
COPY --from=ui /app/dashboard/dist dashboard/dist
ENV PORT=8000
CMD ["sh", "-c", "uvicorn agents.api:app --host 0.0.0.0 --port ${PORT}"]
