import datetime
import json

import holidays
import pytz
import requests

TIMEOUT = 5


def load_json(token):
    with open('./config.json', encoding='utf-8') as f:
        return json.load(f).get(token)


# Check if the stock market is open
def is_market_closed():
    tz = pytz.timezone('America/New_York')
    us_holidays = holidays.US()

    now = datetime.datetime.now(tz)
    open_time = datetime.time(hour=9, minute=30, second=0)
    close_time = datetime.time(hour=16, minute=0, second=0)
    # If a holiday
    if now.strftime('%Y-%m-%d') in us_holidays:
        return True
    # If before 0930 or after 1600
    if (now.time() < open_time) or (now.time() > close_time):
        return True
    # If it's a weekend
    if now.date().weekday() > 4:
        return True

    return False


def pre_market_closed():
    tz = pytz.timezone('America/New_York')
    us_holidays = holidays.US()

    now = datetime.datetime.now(tz)
    pre_open_time = datetime.time(hour=4, minute=00, second=0)
    pre_close_time = datetime.time(hour=9, minute=30, second=00)

    # If a holiday
    if now.strftime('%Y-%m-%d') in us_holidays:
        return True
    if now.time() < pre_open_time or now.time() > pre_close_time:
        return True
    # If it's a weekend
    if now.date().weekday() > 4:
        return True

    return False


def post_market_closed():
    tz = pytz.timezone('America/New_York')
    us_holidays = holidays.US()

    now = datetime.datetime.now(tz)
    post_open_time = datetime.time(hour=16, minute=00, second=0)
    post_close_time = datetime.time(hour=20, minute=00, second=00)

    # If a holiday
    if now.strftime('%Y-%m-%d') in us_holidays:
        return True
    if now.time() < post_open_time or now.time() > post_close_time:
        return True
    # If it's a weekend
    if now.date().weekday() > 4:
        return True

    return False


def url_expander(short_url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
            'Accept-Encoding': 'none',
            'Accept-Language': 'en-US,en;q=0.8',
            'Connection': 'keep-alive'}
        url_response = requests.get(url=short_url, headers=headers, timeout=TIMEOUT)
        return url_response.url
    except requests.exceptions.ConnectionError as e:
        print(e)
        raise requests.exceptions.ConnectionError
    except requests.exceptions.ReadTimeout as e:
        print(e)
        raise requests.exceptions.ReadTimeout


def parse_full_link(url):
    if 'video' in url or 'tiktok.com/v' in url:
        return url

    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.64 Safari/537.36'}
    # headers = {
    #     'User-Agent': f'(Linux; U; Android 10; en_US; Pixel 4; Build/QQ3A.200805.001; Cronet/58.0.2991.0)'}

    r = requests.head(url, timeout=TIMEOUT, headers=headers)
    print(r.headers["location"])
    return r.headers["location"]
