FROM python:3.10-slim AS python-base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1


FROM python-base AS builder

ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN python -m venv /venv
RUN . /venv/bin/activate

ENV POETRY_VERSION=1.8.0
RUN pip install "poetry==$POETRY_VERSION"

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-dev --no-root
COPY . .
RUN poetry build


FROM python-base AS final

COPY --from=builder /venv /venv
COPY --from=builder /dist .

RUN . /venv/bin/activate && pip install *.whl

ARG INSTALL_BROWSER=true
RUN if [ "$INSTALL_BROWSER" = "true" ]; then \
        . /venv/bin/activate && playwright install --with-deps chromium; \
    fi

ENV DA_CURRENCY_CACHE_DIR=/.currency_cache
RUN mkdir $DA_CURRENCY_CACHE_DIR

COPY ./docker/docker-entrypoint.sh ./
ENTRYPOINT ["./docker-entrypoint.sh"]
