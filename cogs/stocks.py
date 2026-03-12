import asyncio
import io
import os
import discord
from discord import app_commands
from discord.ext import commands
import re
from urllib.parse import urlparse
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


def format_large_number(n, prefix=''):
    if n >= 1_000_000_000_000:
        return f'{prefix}{n / 1_000_000_000_000:,.2f}T'
    elif n >= 1_000_000_000:
        return f'{prefix}{n / 1_000_000_000:,.2f}B'
    elif n >= 1_000_000:
        return f'{prefix}{n / 1_000_000:,.2f}M'
    return f'{prefix}{n:,.0f}'


def get_market_status_footer(quote_time):
    tz = pytz.timezone('America/New_York')
    now = datetime.now(tz)
    time_str = now.strftime('%H:%M ET')

    if not Utils.is_market_closed():
        return f'Market Open · {time_str}'
    elif not Utils.pre_market_closed():
        return f'Pre-Market · {time_str}'
    elif not Utils.post_market_closed():
        return f'After Hours · {time_str}'
    else:
        q_time_str = datetime.fromtimestamp(quote_time, tz=tz).strftime('%H:%M ET') if quote_time else time_str
        return f'Market Closed · {q_time_str}'


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
    week52_high = info.get('fiftyTwoWeekHigh')
    week52_low = info.get('fiftyTwoWeekLow')
    market_cap = info.get('marketCap')
    volume = info.get('volume')
    avg_volume = info.get('averageVolume')
    website = info.get('website')

    if change_raw >= 0:
        change_string = f'+{change_raw:.2f}'
        pct_string = f'(+{change_pct_raw:.2f}%)'
    else:
        change_string = f'{change_raw:.2f}'
        pct_string = f'({change_pct_raw:.2f}%)'

    color = 0x85bb65 if change_raw >= 0 else 0xFF0000
    description = f'${latest_price:,.2f} {change_string} {pct_string}'

    embed = discord.Embed(
        title=f'{company_name} (${symbol})',
        url=f'https://finance.yahoo.com/quote/{symbol}',
        description=description,
        color=color
    )

    if website:
        domain = urlparse(website).netloc.lstrip('www.')
        embed.set_thumbnail(url=f'https://img.logo.dev/{domain}?token={os.environ.get("LOGO_DEV_TOKEN", "")}&format=png')

    # Day Range
    if high is not None and low is not None:
        embed.add_field(name='Day Range', value=f'{low:,.2f} — {high:,.2f}', inline=True)

    # Prev Close
    embed.add_field(name='Prev Close', value=f'{prev:,.2f}', inline=True)

    # 52-week Range with progress bar
    if week52_high and week52_low and week52_high != week52_low:
        pct = (latest_price - week52_low) / (week52_high - week52_low)
        pct = max(0.0, min(1.0, pct))
        filled = round(pct * 10)
        bar = '▓' * filled + '░' * (10 - filled)
        embed.add_field(name='52wk Range', value=f'{week52_low:,.2f} {bar} {week52_high:,.2f}', inline=False)

    # Market Cap
    if market_cap:
        embed.add_field(name='Market Cap', value=format_large_number(market_cap, '$'), inline=True)

    # Volume
    if volume:
        vol_str = format_large_number(volume)
        if avg_volume:
            vol_str += f' (avg {format_large_number(avg_volume)})'
        embed.add_field(name='Volume', value=vol_str, inline=True)

    # Pre/post market info when market is closed
    if Utils.is_market_closed():
        extended = closed_market(info)
        if extended:
            embed.add_field(name='Extended Hours', value=extended, inline=False)

    embed.set_footer(text=get_market_status_footer(quote_time))
    return embed


def closed_market(info):
    parts = []

    post_price = info.get('postMarketPrice', 0.0) or 0.0
    if post_price > 0:
        post_change = info.get('postMarketChange', 0.0) or 0.0
        post_pct = info.get('postMarketChangePercent', 0.0) or 0.0
        sign = '+' if post_change >= 0 else ''
        parts.append(f'Post: ${post_price:.2f} {sign}{post_change:.2f} ({sign}{post_pct:.2f}%)')

    pre_price = info.get('preMarketPrice', 0.0) or 0.0
    if pre_price > 0:
        pre_change = info.get('preMarketChange', 0.0) or 0.0
        pre_pct = info.get('preMarketChangePercent', 0.0) or 0.0
        sign = '+' if pre_change >= 0 else ''
        parts.append(f'Pre: ${pre_price:.2f} {sign}{pre_change:.2f} ({sign}{pre_pct:.2f}%)')

    return '\n'.join(parts)


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
