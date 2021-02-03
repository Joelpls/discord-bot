from discord.ext import commands
import discord
import youtube_dl
import os
import re


class Tiktok(commands.Cog):

    def __init__(self, client):
        self.client = client
        self.results = []
        self.directory = 'cogs/tiktokvideos/'

    @commands.Cog.listener()
    async def on_ready(self):
        print('Tiktok cog ready')

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.author.bot:
            # Get Tik Tok links
            matches = re.findall(r'(?:(?:https\:?|ftp):\/\/)?[\w/\-?=%.]+\.[\w/\-&?@=%.]+', message.content, re.MULTILINE)

            if len(matches) > 0:
                vids = list(set(matches))
                self.tiktok_downloader(vids)

                for result in self.results:
                    try:
                        await message.channel.send(file=discord.File(result))
                    except discord.errors.HTTPException:
                        print(f'ERROR: File {result} too large')
                    except FileNotFoundError as e:
                        print(e)
                    if os.path.isfile(result):
                        os.remove(result)

                self.results.clear()

    def tiktok_downloader(self, urls):
        ydl_opts = {
            'outtmpl': f'{self.directory}/%(title)s-%(id)s.%(ext)s'
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            for url in urls:
                info = ydl.extract_info(url, download=False)
                download_target = ydl.prepare_filename(info)
                self.results.append(download_target)
            ydl.download(urls)


def setup(client):
    client.add_cog(Tiktok(client))
