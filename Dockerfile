FROM python:3.13-slim

COPY config.json /
COPY requirements.txt /

RUN pip install -r requirements.txt

COPY bot.py /
COPY Utils.py /
COPY cogs /cogs

CMD [ "python", "./bot.py" ]

