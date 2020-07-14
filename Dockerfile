FROM python:3.8.4

COPY config.json /
COPY requirements.txt /

RUN pip install -r requirements.txt

COPY bot.py /
COPY Slots.py /
COPY Utils.py /
COPY cogs /cogs

CMD [ "python", "./bot.py" ]

