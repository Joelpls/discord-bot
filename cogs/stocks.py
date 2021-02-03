import aiohttp
import discord
import json
from discord.ext import commands
import re
import pytz
from datetime import datetime


def load_json(token):
    with open('./config.json') as f:
        config = json.load(f)
    return config.get(token)


_YAHOO_URL = 'https://query1.finance.yahoo.com/v10/finance/quoteSummary/'

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
            matches = re.findall(pattern_quote, message.content)

            for ticker in set(matches):
                try:
                    response = await get_stock_price_async(ticker)
                    quote_embed = get_yahoo_quote(ticker, response)
                    await message.channel.send(embed=quote_embed)
                except AssertionError:
                    await message.channel.send(f'Unknown symbol: **${ticker.upper()}**')


def setup(client):
    client.add_cog(Stocks(client))


def get_yahoo_quote(ticker: str, response) -> discord.Embed:
    quote_json = response
    quote_result = quote_json.get('quoteSummary', {}).get('result', []).pop().get('price', {})

    symbol = quote_result.get('symbol', ticker.upper())
    company_name = quote_result.get('shortName', ticker.upper())
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

    desc1 = ''.join([str('${:,.2f}'.format(float(latest_price))), " ", change_string, market_percent_string])
    if high is not None and low is not None:
        desc2 = ''.join(['High: ', '{:,.2f}'.format(float(high)), ' Low: ', '{:,.2f}'.format(float(low)), ' Prev: ',
                         '{:,.2f}'.format(float(prev))])
    else:
        desc2 = ''.join(['Prev: ', '{:,.2f}'.format(float(prev))])
    embed = discord.Embed(
        title="".join([company_name, " ($", symbol, ")"]),
        url="https://finance.yahoo.com/quote/" + symbol,
        description=''.join([desc1, '\n', desc2]),
        color=color
    )
    embed.set_footer(text=f'{q_time}')
    return embed


async def get_stock_price_async(ticker: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(_YAHOO_URL + f'{ticker}?modules=price') as response:
            assert 200 == response.status, response.reason
            return await response.json()
