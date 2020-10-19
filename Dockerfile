FROM ubuntu:20.04

COPY requirements.txt /tmp/requirements.txt
ADD ./server /server
WORKDIR /server

RUN apt update \
    && apt install -y python3.8 python3.8-dev python3-pip vim \
    && pip3 install -r /tmp/requirements.txt -i https://mirrors.ustc.edu.cn/pypi/web/simple/ \
    && ln -sfv /server/conf/settings.py.pro /server/conf/settings.py
    # && echo -e "6\n70\n18\n1\n" | apt install -y wkhtmltopdf \

CMD bash /server/run.sh
