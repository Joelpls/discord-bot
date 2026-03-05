import random

import aiohttp
import discord
from discord.ext import commands

EPIC_FREE_GAMES_URL = 'https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions'


async def fetch_free_games():
    """Fetch current and upcoming free games from Epic Games Store."""
    params = {'locale': 'en-US', 'country': 'US', 'allowCountries': 'US'}
    async with aiohttp.ClientSession() as session:
        async with session.get(EPIC_FREE_GAMES_URL, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            data = await resp.json()

    elements = data['data']['Catalog']['searchStore']['elements']
    current_free = []
    upcoming_free = []

    for game in elements:
        promotions = game.get('promotions')
        if not promotions:
            continue

        title = game.get('title', 'Unknown')
        original_price = game.get('price', {}).get('totalPrice', {}).get('fmtPrice', {}).get('originalPrice', '')

        # Resolve store page slug
        slug = game.get('productSlug')
        if not slug:
            mappings = game.get('offerMappings') or game.get('catalogNs', {}).get('mappings') or []
            slug = mappings[0].get('pageSlug') if mappings else game.get('urlSlug', '')
        store_url = f'https://store.epicgames.com/en-US/p/{slug}' if slug else None

        # Get wide image for embed thumbnail
        image_url = None
        for img in game.get('keyImages', []):
            if img.get('type') == 'OfferImageWide':
                image_url = img['url']
                break

        info = {'title': title, 'original_price': original_price, 'store_url': store_url, 'image_url': image_url}

        promo_offers = promotions.get('promotionalOffers', [])
        if promo_offers:
            for group in promo_offers:
                for offer in group.get('promotionalOffers', []):
                    if offer.get('discountSetting', {}).get('discountPercentage') == 0:
                        info['end_date'] = offer.get('endDate', '')
                        current_free.append(info)
                        break
        elif promotions.get('upcomingPromotionalOffers'):
            for group in promotions['upcomingPromotionalOffers']:
                for offer in group.get('promotionalOffers', []):
                    if offer.get('discountSetting', {}).get('discountPercentage') == 0:
                        info['start_date'] = offer.get('startDate', '')
                        upcoming_free.append(info)
                        break

    return current_free, upcoming_free

FEATURE_REQUEST_INSULTS = [
    'Add it yourself, bozo!',
    'Oh wow, what a revolutionary idea. Did you come up with that all by yourself?',
    'Cool idea. Too bad nobody asked.',
    'Noted. Filed directly into the trash.',
    'Incredible. Truly. I\'m in awe of your mediocrity.',
    'That\'s a great idea for someone else\'s bot.',
    'Have you considered not having opinions?',
    'Bold of you to assume anyone will implement that.',
    'Wow. Groundbreaking. Truly never been thought of before.',
    'I\'ll get right on that, right after never.',
]


class Info(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print('Info cog ready')

    @commands.command(name='featurerequest', aliases=['request', 'fr'])
    async def feature_request(self, ctx, *, text):
        """Request a new feature for the discord bot!"""
        insult = random.choice(FEATURE_REQUEST_INSULTS)
        await ctx.send(f'{insult} But if you insist... '
                       f'https://github.com/Joelpls/discord-bot/issues/new?assignees=&labels=&template=feature_request.md&title='
                       f'{text.replace(" ", "%20")}')

    @commands.command()
    async def features(self, ctx):
        """Show a list of automatic bot features"""
        embed = discord.Embed(title='Automatic Features', color=discord.Color.blurple())
        embed.add_field(name='Counting', value='Enforces sequential counting in any channel named "counting". Deletes invalid messages and DMs the correct next number.', inline=False)
        embed.add_field(name='TikTok & Twitter/X', value='Automatically reposts TikTok and Twitter/X video links as a direct playable video.', inline=False)
        embed.add_field(name='YouTube Notifications', value='Posts new videos from subscribed YouTube channels to a designated channel or thread. Manage subscriptions with `!youtube`.', inline=False)
        await ctx.send(embed=embed)

    @commands.command(name='freegames', aliases=['freegame'])
    async def free_games(self, ctx):
        """Show this week's free games from the Epic Store"""
        async with ctx.typing():
            try:
                current, upcoming = await fetch_free_games()
            except Exception as e:
                print(f'Epic Games API error: {e}')
                await ctx.send('<https://www.epicgames.com/store/en-US/free-games>')
                return

        if not current and not upcoming:
            await ctx.send('<https://www.epicgames.com/store/en-US/free-games>')
            return

        for game in current:
            title = game['title']
            price = game['original_price']
            label = f'**{title}** (~~{price}~~ Free)' if price and price != '0' else f'**{title}** (Free)'
            url = game['store_url']
            embed = discord.Embed(title=label, url=url, color=discord.Color.green())
            if game.get('image_url'):
                embed.set_image(url=game['image_url'])
            embed.set_footer(text='Free now on Epic Games Store')
            await ctx.send(embed=embed)

        for game in upcoming:
            title = game['title']
            price = game['original_price']
            label = f'{title} (~~{price}~~)' if price and price != '0' else title
            embed = discord.Embed(title=label, color=discord.Color.greyple(), description='Coming soon')
            embed.set_footer(text='Upcoming free game')
            await ctx.send(embed=embed)

        await ctx.send('<https://www.epicgames.com/store/en-US/free-games>')


async def setup(client):
    await client.add_cog(Info(client))