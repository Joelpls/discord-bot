import os
import discord
import requests
import json
from discord.ext import commands


def load_json(token):
    with open('./config.json') as f:
        config = json.load(f)
    return config.get(token)


def setup(client):
    client.add_cog(Torrents(client))


def get_magnet(search: str) -> discord.Embed:
    """
    Get a magnet link for a torrent.
    Use the backend api for thepiratebay website
    """

    failure = discord.Embed(
        title='Unable to find torrent',
        url=f'https://www.thepiratebay.org/search/{search}',
        description='No Magnet Found'
    )

    try:
        response = requests.get(f'https://apibay.org/q.php?q={search}')
    except requests.ConnectionError:
        print('Unable to reach apibay.org!')
        return failure

    # Top torrent
    target = json.loads(response.content)[0]

    # No torrent found
    if target.get('id') == '0':
        return failure

    # Top torrent magnet link
    desc = f"Magnet: magnet:?xt=urn:btih:{target.get('info_hash')}&dn={target.get('name')}\n\n"
    desc += f"Seeders: {target.get('seeders')}\nLeachers: {target.get('leechers')}\n"
    desc += f"Uploader: {target.get('username')}\nSize:  {target.get('size')}"

    success = discord.Embed(
        title=target.get('name'),
        description=desc
    )
    return success


class Torrents(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print('Torrents cog ready')

    @commands.command()
    async def torrent(self, ctx, *choices: str):
        """
        Get a magnet link for a torrent.
        Usage: !torrent <keywords to earch>
        Example: !torrent last week tonight 1080p
        """

        search_string = '+'.join(choices)
        magnet_embed = get_magnet(search_string)
        await ctx.send(embed=magnet_embed)
