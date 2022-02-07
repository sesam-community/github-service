FROM python:3-alpine
MAINTAINER Hans Erlend Bakken Glad "hans.glad@sesam.io"
COPY ./service /service
WORKDIR /service
RUN apk update
RUN apk add git
RUN apk add openssh
RUN pip install -r requirements.txt
RUN mkdir /data
# install /etc/mime.types, otherwise mimetypes will fail identifying some types
RUN apk add mailcap && \
    rm /var/cache/apk/*

EXPOSE 5000/tcp
ENTRYPOINT ["python"]
CMD ["service.py"]
