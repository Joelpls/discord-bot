import datetime
import xml.etree.ElementTree as ET

import aiohttp
import discord
from discord.ext import commands, tasks

FEED_URL = 'https://www.youtube.com/feeds/videos.xml?channel_id=UCrTNhL_yO3tPTdQ5XgmmWjA'
THREAD_ID = 1170085014189379654
# THREAD_ID = 1478131003624263863 # test server
POLL_MINUTES = 15

NS = {
    'atom': 'http://www.w3.org/2005/Atom',
    'yt': 'http://www.youtube.com/xml/schemas/2015',
    'media': 'http://search.yahoo.com/mrss/',
}


class YouTube(commands.Cog):

    def __init__(self, client):
        self.client = client
        self.posted_ids = set()
        self.poll_feed.start()

    def cog_unload(self):
        self.poll_feed.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        print('YouTube cog ready')

    @tasks.loop(minutes=POLL_MINUTES)
    async def poll_feed(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(FEED_URL, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    resp.raise_for_status()
                    text = await resp.text()
        except Exception as e:
            print(f'YouTube feed fetch failed: {e}')
            return

        root = ET.fromstring(text)
        entry = root.find('atom:entry', NS)
        if entry is None:
            return

        video_id = entry.find('yt:videoId', NS).text
        link = entry.find('atom:link', NS).get('href')
        published_str = entry.find('atom:published', NS).text

        published = datetime.datetime.fromisoformat(published_str)
        now = datetime.datetime.now(datetime.timezone.utc)
        age_seconds = (now - published).total_seconds()

        if age_seconds < POLL_MINUTES * 60 and video_id not in self.posted_ids:
            thread = self.client.get_channel(THREAD_ID)
            if thread:
                await thread.send(link)
                desc_el = entry.find('media:group/media:description', NS)
                if desc_el is not None and desc_el.text:
                    description = desc_el.text
                    truncated = description[:300] + '...' if len(description) > 300 else description
                    embed = discord.Embed(description=truncated, timestamp=published)
                    await thread.send(embed=embed)
                self.posted_ids.add(video_id)

    @poll_feed.before_loop
    async def before_poll(self):
        await self.client.wait_until_ready()


async def setup(client):
    await client.add_cog(YouTube(client))