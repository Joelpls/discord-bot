from discord.ext import commands
import discord
import youtube_dl
import threading
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
            matches = re.findall(r'(?:(?:https\:?|ftp):\/\/)?[\w/\-?=%.]+\.[\w/\-&?=%.]+', message.content, re.MULTILINE)

            if len(matches) > 0:
                threads = []
                for match in set(matches):
                    if 'tiktok.com' in match:
                        thread = threading.Thread(target=self.tiktok_downloader(match))
                        threads.append(thread)
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()

                for result in self.results:
                    await message.channel.send(file=discord.File(result))
                    if os.path.isfile(result):
                        os.remove(result)

                self.results.clear()

    def tiktok_downloader(self, url):
        ydl_opts = {
            'outtmpl': f'{self.directory}/%(title)s-%(id)s.%(ext)s'
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            dl = [url]
            info = ydl.extract_info(url, download=False)
            download_target = ydl.prepare_filename(info)
            ydl.download(dl)
            self.results.append(download_target)


def setup(client):
    client.add_cog(Tiktok(client))
