FROM python:3.10.2-alpine3.15

RUN apk add git 

# dns not working for some reason when building so configuring this for
# this layer
RUN printf "nameserver 8.8.8.8\nnameserver 8.8.4.4\n" > /etc/resolv.conf \
    && git clone https://github.com/OSGConnect/user-account-tracking.git

WORKDIR user-account-tracking

RUN pip3 install -r requirements.txt

# testing
RUN python3 generate_user_report.py --help

ENTRYPOINT ["python3", "generate_user_report.py"]




