import datetime
import os
import re

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks
from pymongo import MongoClient

POLL_MINUTES = 15
ITEMS_PER_PAGE = 10
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')
YOUTUBE_API_BASE = 'https://www.googleapis.com/youtube/v3'

cluster = MongoClient(os.environ.get('MONGODB_ADDRESS'), serverSelectionTimeoutMS=1000)
yt_db = cluster['YouTube']
subs_collection = yt_db['subscriptions']


async def _api_get(session, endpoint, params):
    """Make an authenticated GET request to the YouTube Data API."""
    params['key'] = YOUTUBE_API_KEY
    url = f'{YOUTUBE_API_BASE}/{endpoint}'
    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
        resp.raise_for_status()
        return await resp.json()


async def resolve_channel(session, url_or_handle):
    """Resolve a YouTube URL or @handle to (channel_id, channel_name)."""
    # Extract channel ID directly from URL if possible
    if url_or_handle.startswith('http'):
        # /channel/UC... format
        match = re.search(r'/channel/(UC[a-zA-Z0-9_-]+)', url_or_handle)
        if match:
            channel_id = match.group(1)
            data = await _api_get(session, 'channels', {'part': 'snippet', 'id': channel_id})
            if data['items']:
                return channel_id, data['items'][0]['snippet']['title']
            raise ValueError(f'Channel not found: {channel_id}')

        # /@handle or /c/name or /user/name format — extract the handle/name
        handle_match = re.search(r'youtube\.com/(@[^/?]+)', url_or_handle)
        if handle_match:
            url_or_handle = handle_match.group(1)
        else:
            # /c/name or /user/name
            name_match = re.search(r'youtube\.com/(?:c|user)/([^/?]+)', url_or_handle)
            if name_match:
                url_or_handle = f'@{name_match.group(1)}'

    # Normalize to @handle format
    handle = url_or_handle if url_or_handle.startswith('@') else f'@{url_or_handle}'

    # Use forHandle parameter
    data = await _api_get(session, 'channels', {'part': 'snippet', 'forHandle': handle.lstrip('@')})
    if data.get('items'):
        item = data['items'][0]
        return item['id'], item['snippet']['title']

    # Fallback: search for the channel
    data = await _api_get(session, 'search', {'part': 'snippet', 'q': handle, 'type': 'channel', 'maxResults': 1})
    if data.get('items'):
        item = data['items'][0]
        return item['snippet']['channelId'], item['snippet']['channelTitle']

    raise ValueError(f'Could not find YouTube channel: {url_or_handle}')


async def get_latest_video(session, channel_id):
    """Get the latest video from a channel's uploads playlist. Returns (video_id, snippet) or (None, None)."""
    # The uploads playlist ID is the channel ID with 'UC' replaced by 'UU'
    uploads_playlist_id = 'UU' + channel_id[2:]
    data = await _api_get(session, 'playlistItems', {
        'part': 'snippet',
        'playlistId': uploads_playlist_id,
        'maxResults': 1,
    })
    items = data.get('items', [])
    if not items:
        return None, None
    snippet = items[0]['snippet']
    video_id = snippet['resourceId']['videoId']
    return video_id, snippet


async def is_short(session, video_id):
    """Return True if the video is a YouTube Short. Fails open (returns False on error)."""
    try:
        url = f'https://www.youtube.com/shorts/{video_id}'
        async with session.head(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            return '/shorts/' in str(resp.url)
    except Exception:
        return False


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
        video_id, snippet = await get_latest_video(session, sub['youtube_channel_id'])
        if video_id is None:
            return

        last_video_id = sub.get('last_video_id')

        if last_video_id is not None:
            if video_id == last_video_id:
                return
            should_post = True
        else:
            # Seed was missing at add time: use age check
            published_str = snippet.get('publishedAt')
            if published_str:
                published = datetime.datetime.fromisoformat(published_str.replace('Z', '+00:00'))
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

        if await is_short(session, video_id):
            return

        link = f'https://www.youtube.com/watch?v={video_id}'

        discord_channel = self.client.get_channel(sub['discord_channel_id'])
        if discord_channel is None:
            return

        await discord_channel.send(link)

        description = snippet.get('description', '')
        if description:
            truncated = description[:300] + '...' if len(description) > 300 else description
            published_str = snippet.get('publishedAt')
            published = datetime.datetime.fromisoformat(published_str.replace('Z', '+00:00')) if published_str else discord.utils.utcnow()
            embed = discord.Embed(description=truncated, timestamp=published)
            await discord_channel.send(embed=embed)

    @poll_feed.before_loop
    async def before_poll(self):
        await self.client.wait_until_ready()

    # ── Command group ─────────────────────────────────────────────────────────

    @commands.hybrid_group(name='youtube', invoke_without_command=True)
    async def youtube_group(self, ctx):
        """Manage YouTube subscriptions. Subcommands: add, remove, list"""
        await ctx.send('Usage: `!youtube add <url/@handle> [#channel]`, `!youtube remove <url/@handle>`, `!youtube list`\nNote: Shorts are never posted.')

    @commands.command(name='ytpoll', hidden=True)
    @commands.is_owner()
    async def youtube_poll(self, ctx):
        """(Owner only) Manually trigger the poll loop to test notifications."""
        await ctx.send('Polling all subscriptions now...')
        await self.poll_feed()
        await ctx.send('Poll complete.')

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
                    latest_video_id, _ = await get_latest_video(session, channel_id)
                except Exception as e:
                    print(f'YouTube API fetch failed for {channel_id}: {e}')
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
            lines = []
            for sub in page:
                line = f'**{sub["youtube_channel_name"]}** → <#{sub["discord_channel_id"]}>'
                last = sub.get('last_video_id')
                if last:
                    line += f'\n↳ https://www.youtube.com/watch?v={last}'
                lines.append(line)
            embed.description = '\n\n'.join(lines)
            embed.set_footer(text=f'Page {index + 1}/{len(pages)}')
            return embed

        if len(pages) == 1:
            await ctx.send(embed=make_embed(0))
            return

        view = SubsPaginator(pages, make_embed, ctx.author)
        view.message = await ctx.send(embed=make_embed(0), view=view)


async def setup(client):
    await client.add_cog(YouTube(client))
