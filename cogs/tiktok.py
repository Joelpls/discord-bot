from discord.ext import commands
import discord
import youtube_dl
import os
import re
import praw


class Tiktok(commands.Cog):

    def __init__(self, client):
        self.client = client
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
                vids = []
                for match in set(matches):
                    if 'tiktok.com' in match or 'v.redd.it' in match:
                        vids.append(match)
                    if 'reddit.com' in match:
                        reddit = praw.Reddit(client_id=os.environ.get('REDDIT_CLIENT_ID'),
                                             client_secret=os.environ.get('REDDIT_CLIENT_SECRET'),
                                             user_agent="meme bot for Discord by Joel")
                        
                        submission = reddit.submission(url=match).url
                        if 'v.redd.it' in submission:
                            vids.append(submission)

                if len(vids) > 0:
                    file_names = []
                    self.tiktok_downloader(vids, file_names)

                    for file_name in file_names:
                        try:
                            await message.channel.send(file=discord.File(file_name))
                        except discord.errors.HTTPException:
                            print(f'ERROR: File {file_name} too large')
                        except FileNotFoundError as e:
                            print(e)
                        if os.path.isfile(file_name):
                            os.remove(file_name)

                    file_names.clear()

    def tiktok_downloader(self, urls, file_names):
        ydl_opts = {
            'outtmpl': f'{self.directory}/%(title)s-%(id)s.%(ext)s',
            'max_filesize' : 9000000
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            for url in urls:
                try:
                    info = ydl.extract_info(url, download=False)
                    download_target = ydl.prepare_filename(info)
                    file_names.append(download_target)
                except youtube_dl.utils.DownloadError:
                    urls.remove(url)

            ydl.download(urls)


def setup(client):
    client.add_cog(Tiktok(client))
