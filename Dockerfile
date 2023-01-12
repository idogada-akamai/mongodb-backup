FROM python:3.11.1-alpine3.17 AS python-build

ENV POETRY_VERSION=1.3.0 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PYTHONUNBUFFERED=1

RUN python -m pip install poetry==$POETRY_VERSION

WORKDIR /app
RUN python -m venv /app/venv

COPY pyproject.toml poetry.lock ./
# Allows me to tweak the dependency installation.
ARG POETRY_OPTIONS
RUN . /app/venv/bin/activate \
    && poetry install $POETRY_OPTIONS

# Atlas CLI installation
FROM alpine:3.17.1 AS atlas
ENV ATLAS_CLI_VERSION=1.4.0
RUN apk update && \
    apk add wget tar && \
    tarball_name="mongodb-atlas-cli_${ATLAS_CLI_VERSION}_linux_x86_64" && \
    wget -c https://fastdl.mongodb.org/mongocli/$tarball_name.tar.gz -O - | tar -xz -C /tmp && \
    mv /tmp/$tarball_name/bin/atlas /tmp 

## Beginning of runtime image
FROM  python:3.11.1-alpine3.17 as runtime

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

ENV PATH /app/venv/bin:$PATH

COPY --from=atlas /tmp/atlas /usr/local/bin
COPY --from=python-build /app/venv /app/venv/

RUN apk update && apk add wget jq bash

WORKDIR /app
COPY backup.sh /app/
RUN chmod +x /app/backup.sh
COPY upload_to_s3.py /app/

ENTRYPOINT ["/app/backup.sh"]