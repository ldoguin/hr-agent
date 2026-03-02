FROM python:3.13-slim


# Python
ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

# Poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR='/var/cache/pypoetry' \
    POETRY_HOME='/usr/local' \
    POETRY_VERSION=1.8.3

RUN useradd -m appuser
WORKDIR /app
ENV PIP_ROOT_USER_ACTION=ignore

COPY pyproject.toml poetry.lock  /app/

# Copy application code
ADD svc/ ./svc/
ADD LICENSE ./
ADD email_html_template.html ./
ADD email_text_template.txt ./
ADD burgundydavidluckham-root-certificate.txt ./

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN pip install poetry && poetry config virtualenvs.create false
RUN poetry install --no-root


RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

ADD .env ./
ADD agentcatalog_index.json ./

# Create necessary directories
RUN mkdir -p logs


RUN chown -R appuser:appuser /app
USER appuser

ENV WORKERS=2 BIND=0.0.0.0:8000 TIMEOUT=60 KEEPALIVE=5 AGENT_CATALOG_CONN_ROOT_CERTIFICATE=/app/burgundydavidluckham-root-certificate.txt



RUN  git config --global user.email "bot@couchbase.com" && git config --global user.name "bot" && git init  && git add . && git commit -m"whatever" && agentc init && PYTHONPATH=`pwd` poetry run agentc index svc/prompts/ && PYTHONPATH=`pwd` poetry run agentc index svc/tools/ && PYTHONPATH=`pwd` poetry run agentc publish
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/')" || exit 1

CMD ["bash", "-lc", "exec gunicorn -k uvicorn.workers.UvicornWorker -w ${WORKERS} -b ${BIND} --timeout ${TIMEOUT} --keep-alive ${KEEPALIVE} svc.main:app"]