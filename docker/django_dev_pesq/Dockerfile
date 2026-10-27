FROM python:3.12-slim

WORKDIR /app

RUN pwd

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential git pkg-config default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

COPY ./doc/requirements/requirements.txt /app/requirements.txt
COPY ./doc/requirements/requirements-test.txt /app/requirements-test.txt
COPY ./doc/requirements/requirements-dev.txt /app/requirements-dev.txt

RUN pip install --upgrade pip
RUN pip install -r /app/requirements.txt
RUN pip install -r /app/requirements-test.txt
RUN pip install -r /app/requirements-dev.txt

COPY . /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends locales locales-all \
    && rm -rf /var/lib/apt/lists/*
ENV LC_ALL pt_BR.UTF-8
ENV LANG pt_BR.UTF-8
ENV LANGUAGE pt_BR.UTF-8
