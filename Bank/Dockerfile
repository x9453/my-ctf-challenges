FROM ubuntu:18.04

RUN apt update
RUN apt install -y wget python3 python3-pip

RUN pip3 install web3 py-solc-x

RUN python3 -m solcx.install v0.4.24

COPY app /app

CMD ["python3", "/app/server.py"]
