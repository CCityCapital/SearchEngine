FROM python:3.10-slim-bookworm

# should probably do all this work as non root user
RUN addgroup -gid 1001 appuser && \
    useradd --create-home appuser -g 1001 && mkdir /home/appuser/app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache \
    POETRY_VERSION=1.5.1 \
    POETRY_INSTALLER_MAX_WORKERS=3 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1 \
    PYSETUP_PATH="/opt/pysetup" \
    VENV_PATH="/opt/pysetup/.venv" \
    APP_PATH="/opt/appuser/app" \
    TZ="America/New_York"

ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"

RUN pip install poetry

WORKDIR $APP_PATH/

COPY --chown=appuser:appuser-group ./pyproject.toml $APP_PATH/
COPY --chown=appuser:appuser-group ./poetry.lock $APP_PATH/

RUN poetry install --without dev --no-root --no-cache && rm -rf $POETRY_CACHE_DIR

COPY --chown=appuser:appuser-group corpus_query $APP_PATH/corpus_query

RUN poetry install --without dev

CMD  ["poetry", "run", "uvicorn", "corpus_query.services.api.main:app", "--port", "8000", "--host", "0.0.0.0"]