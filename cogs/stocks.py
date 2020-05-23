import discord
import json
import pyEX as p
from discord.ext import commands
import re


def load_json(token):
    with open('./config.json') as f:
        config = json.load(f)
    return config.get(token)


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
                    quote_embed = get_basic_quote(ticker)
                    await message.channel.send(embed=quote_embed)
                except p.common.PyEXception:
                    await message.channel.send(f'Unknown symbol: {ticker}')


def setup(client):
    client.add_cog(Stocks(client))


def get_basic_quote(ticker: str) -> discord.Embed:
    c = p.Client(api_token=load_json('IEX_pub'), version='v1')
    quote = c.quote(ticker)
    symbol = quote['symbol']
    company_name = quote['companyName']
    latest_price = quote['latestPrice']
    high = quote['high']
    low = quote['low']
    prev = quote['previousClose']
    q_time = quote['latestTime']
    # These values might be null
    try:
        change_percent = round(quote['changePercent'] * 100, 3)
        change = round(quote['change'], 3)
    except TypeError:
        change_percent = None
        change = None

    if change_percent is None:
        market_percent_string = ''
    elif change_percent >= 0:
        market_percent_string = " (+" + str(change_percent) + "%)"
    else:
        market_percent_string = " (" + str(change_percent) + "%)"

    if change is None:
        change_string = ''
    elif change >= 0:
        change_string = "+" + str(change)
    else:
        change_string = str(change)

    desc1 = ''.join([str('${:,.2f}'.format(float(latest_price))), " ", change_string, market_percent_string])
    if high is not None and low is not None:
        desc2 = ''.join(['High: ', '{:,.2f}'.format(float(high)), ' Low: ', '{:,.2f}'.format(float(low)), ' Prev: ',
                         '{:,.2f}'.format(float(prev))])
    else:
        desc2 = ''.join(['Prev: ', '{:,.2f}'.format(float(prev))])
    embed = discord.Embed(
        title="".join([company_name, " ($", symbol, ")"]),
        url="https://www.tradingview.com/symbols/" + symbol,
        description=''.join([desc1, '\n', desc2]),
        color=0x85bb65
    )
    embed.set_footer(text=f'{q_time}')
    return embed
