FROM python:3.11.1-alpine3.17 AS poetry

ENV POETRY_VERSION=1.3.0 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1

RUN python -m pip install poetry==$POETRY_VERSION

FROM poetry AS dependency-install

WORKDIR /app
RUN python -m venv /app/venv

COPY pyproject.toml poetry.lock ./
# Allows me to tweak the dependency installation.
ARG POETRY_OPTIONS
RUN . /app/venv/bin/activate \
    && poetry install $POETRY_OPTIONS

FROM alpine:3.17.2 as download-rclone

ENV RCLONE_VERSION=1.61.1
RUN apk update && \
    apk add wget unzip

WORKDIR /tmp
RUN wget -O rclone.zip https://downloads.rclone.org/v${RCLONE_VERSION}/rclone-v${RCLONE_VERSION}-linux-amd64.zip && \
    unzip rclone.zip && \
    mv rclone-v${RCLONE_VERSION}-linux-amd64/rclone /usr/local/bin

## Beginning of runtime image
FROM poetry as runtime

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

ENV PATH /app/venv/bin:$PATH

COPY --from=download-rclone /usr/local/bin/rclone /usr/local/bin/rclone
COPY --from=dependency-install /app/venv /app/venv/

RUN apk add --update bash

WORKDIR /app
COPY . .

ENTRYPOINT ["python", "backup.py"]