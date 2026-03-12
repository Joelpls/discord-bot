import asyncio
import io
import discord
from discord import app_commands
from discord.ext import commands
import re
import pytz
from datetime import datetime
import yfinance as yf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import Utils


pattern_quote = re.compile(r'[$]([A-Za-z^][^\s]*)')

VALID_PERIODS = ['1d', '5d', '1mo', '3mo', '6mo', '1y', '5y']


class Stocks(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print('Stocks cog ready')

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id != self.client.user.id and '```' not in message.content:
            tickers = re.findall(pattern_quote, message.content)

            for t in set(t.lower() for t in tickers):
                asyncio.get_event_loop().create_task(send_single_quote_embed(t, message))
            return

    @commands.hybrid_command(name='chart', description='Show a price chart for a stock ticker')
    @app_commands.describe(
        ticker='Stock ticker symbol (e.g. MSFT)',
        period='Time period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 5y'
    )
    @app_commands.choices(period=[
        app_commands.Choice(name='1 day', value='1d'),
        app_commands.Choice(name='5 days', value='5d'),
        app_commands.Choice(name='1 month', value='1mo'),
        app_commands.Choice(name='3 months', value='3mo'),
        app_commands.Choice(name='6 months', value='6mo'),
        app_commands.Choice(name='1 year', value='1y'),
        app_commands.Choice(name='5 years', value='5y'),
    ])
    async def chart(self, ctx, ticker: str, period: str = '1mo'):
        """Show a price chart for a stock ticker. Usage: !chart MSFT 1mo"""
        ticker = ticker.upper().lstrip('$')
        period = period.lower()

        if period not in VALID_PERIODS:
            await ctx.send(f'Invalid period. Choose from: {", ".join(VALID_PERIODS)}')
            return

        async with ctx.typing():
            try:
                chart_file, company_name = await asyncio.to_thread(generate_chart, ticker, period)
            except ValueError as e:
                await ctx.send(str(e))
                return

            embed = discord.Embed(
                title=f'{company_name} (${ticker}) — {period}',
                url=f'https://finance.yahoo.com/quote/{ticker}',
                color=discord.Color.blurple()
            )
            embed.set_image(url=f'attachment://{ticker}_chart.png')
            await ctx.send(embed=embed, file=chart_file)


async def setup(client):
    await client.add_cog(Stocks(client))


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
        await update_quote(msg, ticker, 60)

async def update_quote(msg, ticker, length):
    try:
        response = await get_stock_price_async(ticker)
        new_embed = get_yahoo_quote(ticker, response)
        await msg.edit(embed=new_embed)
        await asyncio.sleep(length)
    except AttributeError:
        return


def get_yahoo_quote(ticker: str, info) -> discord.Embed:
    symbol = info.get('symbol', ticker.upper())
    company_name = info.get('shortName', ticker.upper())
    if company_name is None:
        return discord.Embed(title=f'Failed to retrieve ${ticker.upper()}')

    latest_price = info.get('regularMarketPrice', 0.0) or 0.0
    high = info.get('dayHigh')
    low = info.get('dayLow')
    prev = info.get('previousClose', 0.0) or 0.0
    change_raw = info.get('regularMarketChange', 0.0) or 0.0
    change_pct_raw = info.get('regularMarketChangePercent', 0.0) or 0.0
    quote_time = info.get('regularMarketTime')
    q_time = datetime.fromtimestamp(quote_time, tz=pytz.timezone('America/New_York')).strftime('%H:%M:%S %Y-%m-%d')

    change_str = f'{change_raw:.2f}'
    change_pct_str = f'{change_pct_raw:.2f}%'

    if change_raw >= 0:
        market_percent_string = f' (+{change_pct_str})'
        change_string = f'+{change_str}'
    else:
        market_percent_string = f' ({change_pct_str})'
        change_string = change_str

    color = 0x85bb65 if change_raw >= 0 else 0xFF0000

    if Utils.is_market_closed():
        after_market = closed_market(info)
    else:
        after_market = ''

    week52_high = info.get('fiftyTwoWeekHigh')
    week52_low = info.get('fiftyTwoWeekLow')

    return stock_embed(change_string, color, company_name, high, latest_price, low, market_percent_string, prev, q_time, symbol,
                       after_market, week52_high, week52_low)


def stock_embed(change_string, color, company_name, high, latest_price, low, market_percent_string, prev, q_time, symbol,
                after_market, week52_high=None, week52_low=None):
    desc1 = ''.join([str('${:,.2f}'.format(float(latest_price))), " ", change_string, market_percent_string])
    if high is not None and low is not None:
        desc2 = ''.join(['High: ', '{:,.2f}'.format(float(high)), ' Low: ', '{:,.2f}'.format(float(low)), ' Prev: ',
                         '{:,.2f}'.format(float(prev))])
    else:
        desc2 = ''.join(['Prev: ', '{:,.2f}'.format(float(prev))])
    if week52_high is not None and week52_low is not None:
        desc3 = f'52wk High: {week52_high:,.2f}  52wk Low: {week52_low:,.2f}'
    else:
        desc3 = ''
    embed = discord.Embed(
        title="".join([company_name, " ($", symbol, ")"]),
        url="https://finance.yahoo.com/quote/" + symbol,
        description='\n'.join(filter(None, [desc1, desc2, desc3, after_market])),
        color=color
    )
    embed.set_footer(text=f'{q_time}')
    return embed


def closed_market(info):
    postMarketPrice = info.get('postMarketPrice', 0.0) or 0.0
    postMarketChange = info.get('postMarketChange', 0.0) or 0.0
    postMarketChangePercent = info.get('postMarketChangePercent', 0.0) or 0.0
    postMarketTime = info.get('postMarketTime')
    try:
        post_time = datetime.fromtimestamp(postMarketTime, tz=pytz.timezone('America/New_York')).strftime('%H:%M:%S %Y-%m-%d')
    except TypeError:
        post_time = ''

    preMarketPrice = info.get('preMarketPrice', 0.0) or 0.0
    preMarketChange = info.get('preMarketChange', 0.0) or 0.0
    preMarketChangePercent = info.get('preMarketChangePercent', 0.0) or 0.0
    preMarketTime = info.get('preMarketTime')
    try:
        pre_time = datetime.fromtimestamp(preMarketTime, tz=pytz.timezone('America/New_York')).strftime('%H:%M:%S %Y-%m-%d')
    except TypeError:
        pre_time = ''

    if postMarketChange >= 0:
        post_change_string = f'+{postMarketChange:.2f}'
        post_percent_string = f'+{postMarketChangePercent:.2f}%'
    else:
        post_change_string = f'{postMarketChange:.2f}'
        post_percent_string = f'{postMarketChangePercent:.2f}%'

    if postMarketPrice > 0:
        post_market_desc = f'\nPost-market: ${postMarketPrice:.2f} {post_change_string} ({post_percent_string}) {post_time}'
    else:
        post_market_desc = ''

    if preMarketChange >= 0:
        pre_change_string = f'+{preMarketChange:.2f}'
        pre_percent_string = f'+{preMarketChangePercent:.2f}%'
    else:
        pre_change_string = f'{preMarketChange:.2f}'
        pre_percent_string = f'{preMarketChangePercent:.2f}%'

    if preMarketPrice > 0:
        pre_market_desc = f'\nPre-market: ${preMarketPrice:.2f} {pre_change_string} ({pre_percent_string}) {pre_time}'
    else:
        pre_market_desc = ''

    return f'{pre_market_desc}{post_market_desc}'


def generate_chart(ticker: str, period: str):
    t = yf.Ticker(ticker)
    hist = t.history(period=period)

    if hist.empty:
        raise ValueError(f'Unknown symbol: **${ticker}**')

    company_name = t.info.get('shortName', ticker)

    fig, ax = plt.subplots(figsize=(10, 5))

    dates = hist.index
    closes = hist['Close']
    color = '#2ecc71' if closes.iloc[-1] >= closes.iloc[0] else '#e74c3c'

    ax.plot(dates, closes, color=color, linewidth=2)
    ax.fill_between(dates, closes, closes.min(), alpha=0.15, color=color)

    ax.set_title(f'{company_name} (${ticker})', fontsize=16, fontweight='bold')
    ax.set_ylabel('Price ($)', fontsize=12)
    ax.grid(True, alpha=0.3)

    if period == '1d':
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    elif period in ('5d', '1mo'):
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))

    fig.autofmt_xdate()
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=100)
    plt.close(fig)
    buf.seek(0)

    return discord.File(buf, filename=f'{ticker}_chart.png'), company_name


async def get_stock_price_async(ticker: str):
    def fetch():
        t = yf.Ticker(ticker)
        info = t.info
        if not info or info.get('regularMarketPrice') is None:
            raise AssertionError(f'No data for {ticker}')
        return info
    return await asyncio.to_thread(fetch)
