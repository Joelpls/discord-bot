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
import colorsys
from pymongo import MongoClient
import Utils


pattern_quote = re.compile(r'[$]([A-Za-z^][^\s]*)')

VALID_PERIODS = ['1d', '5d', '1mo', '3mo', '6mo', '1y', '5y']

cluster = MongoClient(os.environ.get('MONGODB_ADDRESS'))
stocks_db = cluster['Stocks']
watchlist_collection = stocks_db['watchlists']

WATCHLIST_LIMIT = 15


class Stocks(commands.Cog):

    def __init__(self, client):
        self.client = client

    watchlist_group = app_commands.Group(name='watchlist', description='Manage your stock watchlist')

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

    @app_commands.command(name='compare', description='Compare 2-4 stock tickers on a normalized % change chart')
    @app_commands.describe(
        tickers='Stock ticker symbols separated by spaces (e.g. MSFT AAPL GOOG)',
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
    async def compare(self, interaction: discord.Interaction, tickers: str, period: str = '1mo'):
        """Compare 2-4 tickers on a normalized chart."""
        parts = list(dict.fromkeys(tickers.upper().replace('$', '').split()))
        period = period.lower()

        if period not in VALID_PERIODS:
            await interaction.response.send_message(f'Invalid period. Choose from: {", ".join(VALID_PERIODS)}')
            return

        if len(parts) < 2:
            await interaction.response.send_message('Please provide at least 2 tickers to compare.')
            return

        if len(parts) > 4:
            await interaction.response.send_message('Maximum 4 tickers allowed.')
            return

        await interaction.response.defer()
        try:
            chart_file, valid_tickers = await asyncio.to_thread(generate_compare_chart, parts, period)
        except ValueError as e:
            await interaction.followup.send(str(e))
            return

        title = ' vs '.join(f'${t}' for t in valid_tickers) + f' — {period}'
        embed = discord.Embed(title=title, color=discord.Color.blurple())
        embed.set_image(url='attachment://compare_chart.png')
        await interaction.followup.send(embed=embed, file=chart_file)

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


    # --- /movers ---
    @app_commands.command(name='movers', description='Show top stock market gainers and losers')
    async def movers(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            embed = await asyncio.to_thread(fetch_movers)
        except Exception as e:
            print(f'Movers error: {e}')
            await interaction.followup.send('Failed to fetch market movers. Try again later.')
            return
        await interaction.followup.send(embed=embed)

    # --- /news ---
    @app_commands.command(name='news', description='Show recent news for a stock ticker')
    @app_commands.describe(ticker='Stock ticker symbol (e.g. MSFT)')
    async def news(self, interaction: discord.Interaction, ticker: str):
        ticker = ticker.upper().strip().lstrip('$')
        if not re.match(r'^[A-Za-z0-9^.\-]{1,10}$', ticker):
            await interaction.response.send_message('Invalid ticker symbol.')
            return

        await interaction.response.defer()
        try:
            def fetch_news():
                t = yf.Ticker(ticker)
                return t.news, t.info.get('regularMarketChange', 0) or 0
            articles, change = await asyncio.to_thread(fetch_news)
        except Exception as e:
            print(f'News error: {e}')
            await interaction.followup.send(f'Failed to fetch news for **${ticker}**.')
            return

        if not articles:
            await interaction.followup.send(f'No recent news found for **${ticker}**.')
            return

        lines = []
        for i, article in enumerate(articles[:5], 1):
            content = article.get('content', {})
            title = content.get('title', 'Untitled')
            click_through = content.get('clickThroughUrl') or content.get('canonicalUrl') or {}
            link = click_through.get('url', '')
            provider = content.get('provider') or {}
            publisher = provider.get('displayName', '')
            pub_date = content.get('pubDate', '')
            line = f'{i}. [**{title}**]({link})' if link else f'{i}. **{title}**'
            meta = []
            if publisher:
                meta.append(f'*{publisher}*')
            if pub_date:
                try:
                    ts = int(datetime.fromisoformat(pub_date.replace('Z', '+00:00')).timestamp())
                    meta.append(f'<t:{ts}:R>')
                except (ValueError, OSError):
                    pass
            if meta:
                line += '\n' + ' · '.join(meta)
            lines.append(line)

        embed = discord.Embed(
            title=f'${ticker} — Recent News',
            description='\n'.join(lines),
            color=0x85bb65 if change >= 0 else 0xFF0000,
            url=f'https://finance.yahoo.com/quote/{ticker}'
        )
        await interaction.followup.send(embed=embed)

    # --- /watchlist ---
    @watchlist_group.command(name='add', description='Add a ticker to your watchlist')
    @app_commands.describe(ticker='Stock ticker symbol (e.g. MSFT)')
    async def watchlist_add(self, interaction: discord.Interaction, ticker: str):
        ticker = ticker.upper().strip().lstrip('$')
        if not re.match(r'^[A-Za-z0-9^.\-]{1,10}$', ticker):
            await interaction.response.send_message('Invalid ticker symbol.')
            return

        user_id = interaction.user.id
        guild_id = interaction.guild_id

        doc = watchlist_collection.find_one({'user_id': user_id, 'guild_id': guild_id})
        current_tickers = doc['tickers'] if doc else []

        if ticker in current_tickers:
            await interaction.response.send_message(f'**${ticker}** is already on your watchlist.')
            return

        if len(current_tickers) >= WATCHLIST_LIMIT:
            await interaction.response.send_message(f'Watchlist is full ({WATCHLIST_LIMIT}/{WATCHLIST_LIMIT}). Remove a ticker first.')
            return

        watchlist_collection.update_one(
            {'user_id': user_id, 'guild_id': guild_id},
            {'$addToSet': {'tickers': ticker}},
            upsert=True
        )
        await interaction.response.send_message(f'Added **${ticker}** to your watchlist. ({len(current_tickers) + 1}/{WATCHLIST_LIMIT})')

    @watchlist_group.command(name='remove', description='Remove a ticker from your watchlist')
    @app_commands.describe(ticker='Stock ticker symbol to remove')
    async def watchlist_remove(self, interaction: discord.Interaction, ticker: str):
        ticker = ticker.upper().strip().lstrip('$')
        user_id = interaction.user.id
        guild_id = interaction.guild_id

        doc = watchlist_collection.find_one({'user_id': user_id, 'guild_id': guild_id})
        current_tickers = doc['tickers'] if doc else []

        if ticker not in current_tickers:
            await interaction.response.send_message(f'**${ticker}** is not on your watchlist.')
            return

        watchlist_collection.update_one(
            {'user_id': user_id, 'guild_id': guild_id},
            {'$pull': {'tickers': ticker}}
        )
        await interaction.response.send_message(f'Removed **${ticker}** from your watchlist.')

    @watchlist_remove.autocomplete('ticker')
    async def watchlist_remove_autocomplete(self, interaction: discord.Interaction, current: str):
        doc = watchlist_collection.find_one({'user_id': interaction.user.id, 'guild_id': interaction.guild_id})
        tickers = doc['tickers'] if doc else []
        current = current.upper()
        return [
            app_commands.Choice(name=t, value=t)
            for t in tickers if current in t
        ][:25]

    @watchlist_group.command(name='view', description='View your watchlist with current prices')
    async def watchlist_view(self, interaction: discord.Interaction):
        doc = watchlist_collection.find_one({'user_id': interaction.user.id, 'guild_id': interaction.guild_id})
        tickers = doc['tickers'] if doc else []

        if not tickers:
            await interaction.response.send_message('Your watchlist is empty. Use `/watchlist add` to get started.')
            return

        await interaction.response.defer()
        quotes = await asyncio.to_thread(fetch_watchlist_prices, tickers)

        lines = []
        pct_changes = []
        for t, info in quotes:
            if info is None:
                lines.append(f'[**{t}**](https://finance.yahoo.com/quote/{t}) — data unavailable')
                continue
            name = info.get('shortName', t)
            price = info.get('regularMarketPrice', 0) or 0
            change = info.get('regularMarketChange', 0) or 0
            pct = info.get('regularMarketChangePercent', 0) or 0
            pct_changes.append(pct)
            sign = '+' if change >= 0 else ''
            lines.append(f'[**{t}**](https://finance.yahoo.com/quote/{t}) {name}\n${price:,.2f} {sign}{change:.2f} ({sign}{pct:.2f}%)')

        # Color based on average % change across watchlist
        # deep red (-5%+) → orange → yellow (0%) → green → bright green (+5%+)
        avg_pct = sum(pct_changes) / len(pct_changes) if pct_changes else 0
        clamped = max(-5.0, min(5.0, avg_pct))
        hue = (clamped + 5) / 10.0 * 120 / 360.0  # 0° (red) to 120° (green)
        r, g, b = colorsys.hls_to_rgb(hue, 0.45, 0.8)
        color = (int(r * 255) << 16) | (int(g * 255) << 8) | int(b * 255)

        embed = discord.Embed(
            title='Your Watchlist',
            description='\n\n'.join(lines),
            color=color
        )
        footer = get_market_status_footer(None) + f' · {len(tickers)}/{WATCHLIST_LIMIT} slots used'
        embed.set_footer(text=footer)
        await interaction.followup.send(embed=embed)


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

    dates = hist.index.tz_localize(None)
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


COMPARE_COLORS = ['#2ecc71', '#3498db', '#e74c3c', '#f39c12']


def generate_compare_chart(tickers: list, period: str):
    valid_tickers = []
    histories = []

    for ticker in tickers:
        t = yf.Ticker(ticker)
        hist = t.history(period=period)
        if not hist.empty:
            name = t.info.get('shortName', ticker)
            if len(name) > 20:
                name = name[:18] + '..'
            valid_tickers.append((ticker, name))
            histories.append(hist)

    if len(valid_tickers) < 2:
        raise ValueError('Need at least 2 valid tickers to compare.')

    fig, ax = plt.subplots(figsize=(10, 5))

    for i, ((ticker, name), hist) in enumerate(zip(valid_tickers, histories)):
        dates = hist.index.tz_localize(None)
        closes = hist['Close']
        pct_change = (closes / closes.iloc[0] - 1) * 100
        color = COMPARE_COLORS[i % len(COMPARE_COLORS)]
        ax.plot(dates, pct_change, color=color, linewidth=2, label=f'{ticker} ({name})')

    title = ' vs '.join(t[0] for t in valid_tickers) + f' — {period}'
    ax.set_title(title, fontsize=16, fontweight='bold')
    ax.set_ylabel('% Change', fontsize=12)
    ax.axhline(y=0, color='white', linewidth=0.8, alpha=0.5)
    ax.legend(fontsize=12)
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

    return discord.File(buf, filename='compare_chart.png'), [t[0] for t in valid_tickers]


async def get_stock_price_async(ticker: str):
    def fetch():
        t = yf.Ticker(ticker)
        info = t.info
        if not info or info.get('regularMarketPrice') is None:
            raise AssertionError(f'No data for {ticker}')
        return info
    return await asyncio.to_thread(fetch)


def fetch_movers():
    lines_gainers = []
    lines_losers = []
    price_sum = 0

    result = yf.screen('day_gainers')
    for q in result['quotes'][:5]:
        symbol = q.get('symbol', '?')
        name = q.get('shortName', '')
        price = q.get('regularMarketPrice', 0)
        pct = q.get('regularMarketChangePercent', 0)
        vol = q.get('regularMarketVolume', 0)
        price_sum += int(price * 100)
        lines_gainers.append(
            f'[**{symbol}**](https://finance.yahoo.com/quote/{symbol}) {name} — ${price:,.2f} (+{pct:.2f}%) Vol: {format_large_number(vol)}'
        )

    result = yf.screen('day_losers')
    for q in result['quotes'][:5]:
        symbol = q.get('symbol', '?')
        name = q.get('shortName', '')
        price = q.get('regularMarketPrice', 0)
        pct = q.get('regularMarketChangePercent', 0)
        vol = q.get('regularMarketVolume', 0)
        price_sum += int(price * 100)
        lines_losers.append(
            f'[**{symbol}**](https://finance.yahoo.com/quote/{symbol}) {name} — ${price:,.2f} ({pct:.2f}%) Vol: {format_large_number(vol)}'
        )

    hue = (price_sum % 360) / 360.0
    r, g, b = colorsys.hls_to_rgb(hue, 0.5, 0.7)
    color = (int(r * 255) << 16) | (int(g * 255) << 8) | int(b * 255)

    embed = discord.Embed(title='Market Movers', color=color)
    embed.add_field(name='Top Gainers', value='\n'.join(lines_gainers), inline=False)
    embed.add_field(name='Top Losers', value='\n'.join(lines_losers), inline=False)
    embed.set_footer(text=get_market_status_footer(None))
    return embed


def fetch_watchlist_prices(tickers):
    results = []
    for t in tickers:
        try:
            info = yf.Ticker(t).info
            results.append((t, info))
        except Exception:
            results.append((t, None))
    return results
