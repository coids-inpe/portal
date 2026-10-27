FROM python:3.12-slim

WORKDIR /app

RUN pwd

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

COPY ./doc/requirements/requirements.txt /app/requirements.txt

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential git pkg-config default-libmysqlclient-dev locales locales-all sshpass \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r /app/requirements.txt gunicorn

COPY . /app


ENV LC_ALL pt_BR.UTF-8
ENV LANG pt_BR.UTF-8
ENV LANGUAGE pt_BR.UTF-8

