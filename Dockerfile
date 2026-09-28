FROM python:3.12-slim
WORKDIR /app
ENV RUFF_CACHE_DIR=/tmp/ruff-cache
COPY pyproject.toml ./
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY catalog ./catalog
RUN pip install --no-cache-dir --no-deps .
COPY fixtures ./fixtures
COPY tests ./tests
RUN useradd --create-home catalog && mkdir reports && chown catalog:catalog reports
USER catalog
EXPOSE 8000
CMD ["uvicorn", "catalog.api:app", "--host", "0.0.0.0", "--port", "8000"]
