import datetime
import os
import re
import xml.etree.ElementTree as ET

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks
from pymongo import MongoClient

POLL_MINUTES = 15
ITEMS_PER_PAGE = 10

BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

NS = {
    'atom': 'http://www.w3.org/2005/Atom',
    'yt': 'http://www.youtube.com/xml/schemas/2015',
    'media': 'http://search.yahoo.com/mrss/',
}

cluster = MongoClient(os.environ.get('MONGODB_ADDRESS'), serverSelectionTimeoutMS=1000)
yt_db = cluster['YouTube']
subs_collection = yt_db['subscriptions']


async def resolve_channel(session, url_or_handle):
    """Resolve a YouTube URL or @handle to (channel_id, channel_name)."""
    if not url_or_handle.startswith('http'):
        handle = url_or_handle if url_or_handle.startswith('@') else f'@{url_or_handle}'
        url = f'https://www.youtube.com/{handle}'
    else:
        url = url_or_handle

    async with session.get(url, headers=BROWSER_HEADERS, timeout=aiohttp.ClientTimeout(total=15)) as resp:
        resp.raise_for_status()
        text = await resp.text()

    channel_id_match = re.search(r'"externalId":"([^"]+)"', text)
    if not channel_id_match:
        raise ValueError(f'Could not find channel ID on page: {url}')
    channel_id = channel_id_match.group(1)

    name_match = re.search(r'"channelName":"([^"]+)"', text)
    if name_match:
        channel_name = name_match.group(1)
    else:
        title_match = re.search(r'<title>([^<]+)</title>', text)
        channel_name = title_match.group(1).replace(' - YouTube', '').strip() if title_match else channel_id

    return channel_id, channel_name


async def get_latest_video_id(session, channel_id):
    """Fetch the RSS feed and return the latest video_id, or None."""
    feed_url = f'https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}'
    async with session.get(feed_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
        resp.raise_for_status()
        text = await resp.text()
    root = ET.fromstring(text)
    entry = root.find('atom:entry', NS)
    if entry is None:
        return None
    vid_el = entry.find('yt:videoId', NS)
    return vid_el.text if vid_el is not None else None


class SubsPaginator(discord.ui.View):

    def __init__(self, pages, make_embed, author):
        super().__init__(timeout=60)
        self.pages = pages
        self.make_embed = make_embed
        self.author = author
        self.index = 0
        self._update_buttons()

    def _update_buttons(self):
        self.prev_button.disabled = self.index == 0
        self.next_button.disabled = self.index == len(self.pages) - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message('This is not your list.', ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

    @discord.ui.button(label='◀', style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.make_embed(self.index), view=self)

    @discord.ui.button(label='▶', style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.make_embed(self.index), view=self)


class YouTube(commands.Cog):

    def __init__(self, client):
        self.client = client
        self.poll_feed.start()

    def cog_unload(self):
        self.poll_feed.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        print('YouTube cog ready')

    # ── Poll loop ─────────────────────────────────────────────────────────────

    @tasks.loop(minutes=POLL_MINUTES)
    async def poll_feed(self):
        subs = list(subs_collection.find({}))
        if not subs:
            return

        async with aiohttp.ClientSession() as session:
            for sub in subs:
                try:
                    await self._check_sub(session, sub)
                except Exception as e:
                    print(f'YouTube poll error for {sub.get("youtube_channel_name")}: {e}')

    async def _check_sub(self, session, sub):
        feed_url = f'https://www.youtube.com/feeds/videos.xml?channel_id={sub["youtube_channel_id"]}'
        async with session.get(feed_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            resp.raise_for_status()
            text = await resp.text()

        root = ET.fromstring(text)
        entry = root.find('atom:entry', NS)
        if entry is None:
            return

        vid_el = entry.find('yt:videoId', NS)
        if vid_el is None:
            return
        video_id = vid_el.text

        last_video_id = sub.get('last_video_id')

        if last_video_id is not None:
            # Normal case: only post if it's a new video
            if video_id == last_video_id:
                return
            should_post = True
        else:
            # Seed was missing (RSS was down at add time): use age check
            published_el = entry.find('atom:published', NS)
            if published_el is not None:
                published = datetime.datetime.fromisoformat(published_el.text)
                age_seconds = (datetime.datetime.now(datetime.timezone.utc) - published).total_seconds()
                should_post = age_seconds < POLL_MINUTES * 60
            else:
                should_post = False

        subs_collection.update_one(
            {'_id': sub['_id']},
            {'$set': {'last_video_id': video_id}}
        )

        if not should_post:
            return

        link_el = entry.find('atom:link', NS)
        link = link_el.get('href') if link_el is not None else f'https://www.youtube.com/watch?v={video_id}'

        discord_channel = self.client.get_channel(sub['discord_channel_id'])
        if discord_channel is None:
            return

        await discord_channel.send(link)

        desc_el = entry.find('media:group/media:description', NS)
        if desc_el is not None and desc_el.text:
            description = desc_el.text
            truncated = description[:300] + '...' if len(description) > 300 else description
            published_el = entry.find('atom:published', NS)
            published = datetime.datetime.fromisoformat(published_el.text) if published_el is not None else discord.utils.utcnow()
            embed = discord.Embed(description=truncated, timestamp=published)
            await discord_channel.send(embed=embed)

    @poll_feed.before_loop
    async def before_poll(self):
        await self.client.wait_until_ready()

    # ── Command group ─────────────────────────────────────────────────────────

    @commands.hybrid_group(name='youtube', invoke_without_command=True)
    async def youtube_group(self, ctx):
        """Manage YouTube subscriptions. Subcommands: add, remove, list"""
        await ctx.send('Usage: `!youtube add <url/@handle> [#channel]`, `!youtube remove <url/@handle>`, `!youtube list`')

    @youtube_group.command(name='add')
    @app_commands.describe(
        url_or_handle='YouTube channel URL or @handle (e.g. @redlettermedia)',
        discord_channel='Channel or thread to post videos in (defaults to current)',
    )
    async def youtube_add(self, ctx, url_or_handle: str, discord_channel: discord.TextChannel | discord.Thread = None):
        """Subscribe to a YouTube channel. Defaults to current channel/thread."""
        target_channel = discord_channel or ctx.channel

        async with ctx.typing():
            async with aiohttp.ClientSession() as session:
                try:
                    channel_id, channel_name = await resolve_channel(session, url_or_handle)
                except Exception as e:
                    await ctx.send(f'Could not resolve YouTube channel: {e}')
                    return

                existing = subs_collection.find_one({
                    'guild_id': ctx.guild.id,
                    'youtube_channel_id': channel_id,
                })
                if existing:
                    await ctx.send(f'Already subscribed to **{channel_name}** in <#{existing["discord_channel_id"]}>.')
                    return

                try:
                    latest_video_id = await get_latest_video_id(session, channel_id)
                except Exception as e:
                    print(f'YouTube RSS fetch failed for {channel_id}: {e}')
                    latest_video_id = None

        subs_collection.insert_one({
            'guild_id': ctx.guild.id,
            'youtube_channel_id': channel_id,
            'youtube_channel_name': channel_name,
            'discord_channel_id': target_channel.id,
            'last_video_id': latest_video_id,
        })
        await ctx.send(f'Subscribed to **{channel_name}** → <#{target_channel.id}>')

    @youtube_group.command(name='remove')
    @app_commands.describe(url_or_handle='YouTube channel URL, @handle, or pick from the list')
    async def youtube_remove(self, ctx, url_or_handle: str):
        """Unsubscribe from a YouTube channel."""
        # If the value is already a channel ID (selected via autocomplete), skip resolve
        existing = subs_collection.find_one({
            'guild_id': ctx.guild.id,
            'youtube_channel_id': url_or_handle,
        })
        if existing:
            channel_id = existing['youtube_channel_id']
            channel_name = existing['youtube_channel_name']
        else:
            async with ctx.typing():
                async with aiohttp.ClientSession() as session:
                    try:
                        channel_id, channel_name = await resolve_channel(session, url_or_handle)
                    except Exception as e:
                        await ctx.send(f'Could not resolve YouTube channel: {e}')
                        return

        result = subs_collection.delete_one({
            'guild_id': ctx.guild.id,
            'youtube_channel_id': channel_id,
        })
        if result.deleted_count:
            await ctx.send(f'Unsubscribed from **{channel_name}**.')
        else:
            await ctx.send(f'No subscription found for **{channel_name}** in this server.')

    @youtube_remove.autocomplete('url_or_handle')
    async def remove_autocomplete(self, interaction: discord.Interaction, current: str):
        subs = list(subs_collection.find({'guild_id': interaction.guild_id}))
        return [
            app_commands.Choice(name=sub['youtube_channel_name'], value=sub['youtube_channel_id'])
            for sub in subs
            if current.lower() in sub['youtube_channel_name'].lower()
        ][:25]

    @youtube_group.command(name='list')
    async def youtube_list(self, ctx):
        """List all YouTube subscriptions for this server, paginated."""
        subs = list(subs_collection.find({'guild_id': ctx.guild.id}))
        if not subs:
            await ctx.send('No YouTube subscriptions in this server.')
            return

        pages = [subs[i:i + ITEMS_PER_PAGE] for i in range(0, len(subs), ITEMS_PER_PAGE)]

        def make_embed(index):
            page = pages[index]
            embed = discord.Embed(title='YouTube Subscriptions', color=discord.Color.red())
            lines = [f'**{sub["youtube_channel_name"]}** → <#{sub["discord_channel_id"]}>' for sub in page]
            embed.description = '\n'.join(lines)
            embed.set_footer(text=f'Page {index + 1}/{len(pages)}')
            return embed

        if len(pages) == 1:
            await ctx.send(embed=make_embed(0))
            return

        view = SubsPaginator(pages, make_embed, ctx.author)
        view.message = await ctx.send(embed=make_embed(0), view=view)


async def setup(client):
    await client.add_cog(YouTube(client))
