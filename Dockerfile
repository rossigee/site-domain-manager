FROM alpine
RUN apk -U add \
    python3-dev libffi-dev openssl-dev build-base \
    py3-pip \
    py3-sqlalchemy \
    py3-mysqlclient

# Add python deps so (re)building source in next stage is rapid
RUN pip3 install \
    requests \
    gunicorn \
    uvicorn \
    starlette \
    databases \
    orm \
    boto3 \
    dnspython \
    kubernetes \
    aiohttp \
    aiomysql \
    python-multipart

# Add/build/install source
ADD . /src
RUN cd /src && \
    python3 setup.py sdist && \
    pip3 install dist/site-domain-manager-0.0.1.tar.gz

CMD gunicorn -w 1 --bind=0.0.0.0:8000 -k uvicorn.workers.UvicornWorker sdmgr.app:app

EXPOSE 8000
