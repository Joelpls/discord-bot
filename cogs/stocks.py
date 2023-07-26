import asyncio
import aiohttp
import discord
import json
from discord.ext import commands
import re
import pytz
from datetime import datetime
import Utils


def load_json(token):
    with open('./config.json') as f:
        config = json.load(f)
    return config.get(token)


_YAHOO_URL = 'https://query2.finance.yahoo.com/v11/finance/quoteSummary/'

pattern_quote = re.compile(r'[$]([A-Za-z]+)[+]?')


class Stocks(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print('Stocks cog ready')

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id != self.client.user.id:
            tickers = re.findall(pattern_quote, message.content)

            for t in set(t.lower() for t in tickers):
                asyncio.get_event_loop().create_task(send_single_quote_embed(t, message))
            return


def setup(client):
    client.add_cog(Stocks(client))


async def send_single_quote_embed(ticker, message):
    try:
        response = await get_stock_price_async(ticker)
        quote_embed = get_yahoo_quote(ticker, response)
        msg = await message.channel.send(embed=quote_embed)
        await update_stock_embed(ticker, msg)
    except AssertionError:
        await message.channel.send(f'Unknown symbol: **${ticker.upper()}**')


async def update_stock_embed(ticker, msg):
    await asyncio.sleep(5)

    while not Utils.is_market_closed() \
            or not Utils.post_market_closed() \
            or not Utils.pre_market_closed():
        await update_quote(msg, ticker, 5)

async def update_quote(msg, ticker, length):
    try:
        response = await get_stock_price_async(ticker)
        new_embed = get_yahoo_quote(ticker, response)
        await msg.edit(embed=new_embed)
        await asyncio.sleep(length)
    except AttributeError:
        return


def get_yahoo_quote(ticker: str, response) -> discord.Embed:
    quote_json = response
    quote_result = quote_json.get('quoteSummary', {}).get('result', []).pop().get('price', {})

    symbol = quote_result.get('symbol', ticker.upper())
    company_name = quote_result.get('shortName', ticker.upper())
    if company_name is None:
        return discord.Embed(title=f'Failed to retrieve ${ticker.upper()}')

    latest_price = quote_result.get('regularMarketPrice', {}).get('raw', 0.00)
    high = quote_result.get('regularMarketDayHigh', {}).get('raw', 0.00)
    low = quote_result.get('regularMarketDayLow', {}).get('raw', 0.00)
    prev = quote_result.get('regularMarketPreviousClose', {}).get('raw', 0.00)
    change = quote_result.get('regularMarketChange', {}).get('fmt', 0.00)
    change_percent = quote_result.get('regularMarketChangePercent', {}).get('fmt', 0.00)
    quote_time = quote_result.get('regularMarketTime', {})
    q_time = datetime.fromtimestamp(quote_time, tz=pytz.timezone('America/New_York')).strftime('%H:%M:%S %Y-%m-%d')

    if float(change_percent.strip('%')) >= 0:
        market_percent_string = " (+" + change_percent + ")"
    else:
        market_percent_string = " (" + change_percent + ")"

    color = 0x85bb65  # Dollar Bill Green
    if float(change.strip('%')) >= 0:
        change_string = "+" + change
    else:
        change_string = change
        color = 0xFF0000  # Red

    if Utils.is_market_closed():
        after_market = closed_market(quote_result)
    else:
        after_market = ''

    return stock_embed(change_string, color, company_name, high, latest_price, low, market_percent_string, prev, q_time, symbol,
                       after_market)


def stock_embed(change_string, color, company_name, high, latest_price, low, market_percent_string, prev, q_time, symbol,
                after_market):
    desc1 = ''.join([str('${:,.2f}'.format(float(latest_price))), " ", change_string, market_percent_string])
    if high is not None and low is not None:
        desc2 = ''.join(['High: ', '{:,.2f}'.format(float(high)), ' Low: ', '{:,.2f}'.format(float(low)), ' Prev: ',
                         '{:,.2f}'.format(float(prev))])
    else:
        desc2 = ''.join(['Prev: ', '{:,.2f}'.format(float(prev))])
    embed = discord.Embed(
        title="".join([company_name, " ($", symbol, ")"]),
        url="https://finance.yahoo.com/quote/" + symbol,
        description=''.join([desc1, '\n', desc2, '\n', after_market]),
        color=color
    )
    embed.set_footer(text=f'{q_time}')
    return embed


def closed_market(quote_result):
    postMarketPrice = quote_result.get('postMarketPrice', {}).get('raw', 0.00)
    postMarketChange = quote_result.get('postMarketChange', {}).get('fmt', 0.00)
    postMarketChangePercent = quote_result.get('postMarketChangePercent', {}).get('fmt', 0.00)
    postMarketTime = quote_result.get('postMarketTime', {})
    try:
        post_time = datetime.fromtimestamp(postMarketTime, tz=pytz.timezone('America/New_York')).strftime('%H:%M:%S %Y-%m-%d')
    except TypeError:
        post_time = ''

    preMarketPrice = quote_result.get('preMarketPrice', {}).get('raw', 0.00)
    preMarketChange = quote_result.get('preMarketChange', {}).get('fmt', 0.00)
    preMarketChangePercent = quote_result.get('preMarketChangePercent', {}).get('fmt', 0.00)
    preMarketTime = quote_result.get('preMarketTime', {})
    try:
        pre_time = datetime.fromtimestamp(preMarketTime, tz=pytz.timezone('America/New_York')).strftime('%H:%M:%S %Y-%m-%d')
    except TypeError:
        pre_time = ''

    if float(postMarketChange) > 0:
        post_change_string = f'+{postMarketChange}'
        post_percent_string = f'+{postMarketChangePercent}'
    else:
        post_change_string = postMarketChange
        post_percent_string = postMarketChangePercent

    if postMarketPrice > 0 and post_change_string != 0:
        post_market_desc = f'\nPost-market: ${postMarketPrice} {post_change_string} ({post_percent_string}) {post_time}'
    else:
        post_market_desc = ''

    if float(preMarketChange) > 0:
        pre_change_string = f'+{preMarketChange}'
        pre_percent_string = f'+{preMarketChangePercent}'
    else:
        pre_change_string = preMarketChange
        pre_percent_string = preMarketChangePercent

    if preMarketPrice > 0 and pre_change_string != 0:
        pre_market_desc = f'\nPre-market: ${preMarketPrice} {pre_change_string} ({pre_percent_string}) {pre_time}'
    else:
        pre_market_desc = ''

    return f'{pre_market_desc}{post_market_desc}'


async def get_stock_price_async(ticker: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(_YAHOO_URL + f'?symbol={ticker}&modules=price') as response:
            assert 200 == response.status, response.reason
            return await response.json()
