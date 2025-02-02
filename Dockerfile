FROM python:3.7-alpine
LABEL Description="Runs Magpie AuthN/AuthZ service for REST-API and UI interfaces."
LABEL Maintainer="Francis Charette-Migneault <francis.charette-migneault@crim.ca>"
LABEL Vendor="CRIM"

# the cron service depends on the $MAGPIE_DIR environment variable
ENV MAGPIE_DIR=/opt/local/src/magpie
ENV MAGPIE_ENV_DIR=$MAGPIE_DIR/env
WORKDIR $MAGPIE_DIR

# magpie cron service
COPY magpie-cron /etc/cron.d/magpie-cron
RUN chmod 0644 /etc/cron.d/magpie-cron
RUN touch ~/magpie_cron_status.log
# set /etc/environment so that cron runs using the environment variables set by docker
RUN env >> /etc/environment

COPY magpie/__init__.py magpie/__meta__.py $MAGPIE_DIR/magpie/
COPY requirements* setup.py README.rst HISTORY.rst $MAGPIE_DIR/

RUN apk update \
    && apk add \
        bash \
        postgresql-libs \
        py-pip \
        libxslt-dev \
    && apk add --virtual .build-deps \
        supervisor \
        gcc \
        libffi-dev \
        python-dev \
        musl-dev \
        postgresql-dev \
    && pip install --no-cache-dir --upgrade pip setuptools \
    && pip install --no-cache-dir -e $MAGPIE_DIR \
    && apk --purge del .build-deps

COPY ./ $MAGPIE_DIR

# equivalent of `make install` without conda env and pre-installed packages
RUN pip install --no-dependencies -e $MAGPIE_DIR
# equivalent of `make cron start` without conda env
CMD crond && gunicorn -b 0.0.0.0:2001 --paste $MAGPIE_DIR/config/magpie.ini --workers 10 --preload
