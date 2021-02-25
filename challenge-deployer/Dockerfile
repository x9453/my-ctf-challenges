FROM ubuntu:20.04

RUN apt-get update && apt-get install -y wget python3 python3-pip
RUN pip3 install web3 py-solc-x
RUN python3 -m solcx.install v0.5.17

WORKDIR /app
CMD ["python3", "server.py"]
