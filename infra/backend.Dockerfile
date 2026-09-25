FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app/backend
COPY requirements.lock pyproject.toml ./
COPY app ./app
RUN pip install -r requirements.lock && pip install --no-deps . \
    && useradd --create-home --uid 10001 app
COPY migrations ./migrations
COPY alembic.ini ./
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
