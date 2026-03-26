# Creating a python base with shared environment variables
FROM python:3.10.0-slim as python-base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1


# create 'builder' stage to install dependencies and build `discogs_alert`
FROM python-base as builder

ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# create & activate venv
RUN python -m venv /venv
RUN . /venv/bin/activate

# install Poetry (respects $POETRY_VERSION & $POETRY_HOME)
ENV POETRY_VERSION=1.8.0
RUN pip install "poetry==$POETRY_VERSION"

# gcc/python3-dev needed for building some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends gcc python3-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# install dependencies & create build version of package
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-dev --no-root
COPY . .
RUN poetry build


# create lightweight 'final' stage with which to run discogs alert
FROM python-base as final

# copy everything we need & install `discogs_alert` from whl
COPY --from=builder /venv /venv
COPY --from=builder /dist .

RUN . /venv/bin/activate && pip install *.whl

# Install Playwright Chromium only if not using an external CDP endpoint.
# When DA_CDP_ENDPOINT is set (e.g. Lightpanda sidecar), this step can be
# skipped by building with --build-arg INSTALL_BROWSER=false
ARG INSTALL_BROWSER=true
RUN if [ "$INSTALL_BROWSER" = "true" ]; then \
        . /venv/bin/activate && playwright install --with-deps chromium; \
    fi

# Create a directory in which to cache current conversion dicts
ENV DA_CURRENCY_CACHE_DIR=/.currency_cache
RUN mkdir $DA_CURRENCY_CACHE_DIR

# run entrypoint
COPY ./docker/docker-entrypoint.sh ./
ENTRYPOINT ["./docker-entrypoint.sh"]
