from discord.ext import commands
import discord
import youtube_dl
import os
import re
import praw
import asyncio
import uuid
import yt_dlp
import urlexpander
import Utils

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
                    if 'tiktok.com' in match:
                        tiktokurl = Utils.parse_full_link(match)
                        if 'video' not in tiktokurl:
                            continue
                        vids.append(tiktokurl)
                    if 'v.redd.it' in match or 'twitter.com' in match or 'x.com' in match:
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

                    # msgs = []
                    # msg = None
                    for file_name in file_names:
                        try:
                            msg = await message.channel.send(file=discord.File(file_name))
                            # msgs.append(msg)

                        except discord.errors.HTTPException:
                            print(f'ERROR: File {file_name} too large')
                        except FileNotFoundError as e:
                            print(f'ERROR {e}')
                        if os.path.isfile(file_name):
                            os.remove(file_name)
                    file_names.clear()

                    # if msg:
                    #     await msg.add_reaction('🗑️')
                    # else:
                    #     return
                    #
                    # # Only delete if the person who sent the message reacts.
                    # def check(reaction, user):
                    #     return user == message.author and str(reaction.emoji) == '🗑️'
                    #
                    # # Wait for the waste basket emoji or remove after 2 minutes.
                    # try:
                    #     reaction, user = await self.client.wait_for('reaction_add', timeout=120, check=check)
                    # except asyncio.TimeoutError:
                    #     await msg.remove_reaction(emoji='🗑️', member=message.guild.me)
                    # else:
                    #     for m in msgs:
                    #         await m.delete()

    @commands.command(hidden=True)
    async def deletemsg(self, ctx, msg_id):
        if ctx.author.id == 413139799453597698:
            msg = await ctx.fetch_message(msg_id)
            await msg.delete()
            await ctx.message.delete()

    def tiktok_downloader(self, urls, file_names):
        ydl_opts = {
            'format': '[vcodec=h264]',
            'outtmpl': f'{self.directory}/%(uploader)s-%(uploader_id)s-%(id)s-%(upload_date)s-{str(uuid.uuid4())[:4]}.%(ext)s',
            'max_filesize': 26000000,
            'ignoreerrors': True,
            'verbose': True
        }
        ydl_opts_twitter_x = {
            'outtmpl': f'{self.directory}/%(title)s-%(id)s-{str(uuid.uuid4())[:8]}.%(ext)s',
            'max_filesize': 26000000,
            'ignoreerrors': True,
            'verbose': True,
            'extractor_args': 'twitter:api=syndication'
        }
        ydl_opts_not_tiktok = {
            'outtmpl': f'{self.directory}/%(title)s-%(id)s-{str(uuid.uuid4())[:8]}.%(ext)s',
            'max_filesize': 26000000,
            'ignoreerrors': True,
            'verbose': True
        }
        tiktok_urls = [x for x in urls if 'tiktok.com' in x]
        twitter_and_x_urls = [x for x in urls if 'twitter.com' in x or 'x.com' in x]
        not_tiktoks = [x for x in urls if 'tiktok.com' not in x and 'twitter.com' not in x and 'x.com' not in x]

        self.yt_downloader(file_names, tiktok_urls, ydl_opts)
        self.yt_downloader(file_names, twitter_and_x_urls, ydl_opts_twitter_x)
        self.yt_downloader(file_names, not_tiktoks, ydl_opts_not_tiktok)

    def yt_downloader(self, file_names, urls, ydl_opts):
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            for url in urls:
                try:
                    info = ydl.extract_info(url, download=False)
                    download_target = ydl.prepare_filename(info)
                    file_names.append(download_target)
                except yt_dlp.utils.DownloadError as e:
                    urls.remove(url)
                    print(f'ERROR {e}')

            ydl.download(urls)


def setup(client):
    client.add_cog(Tiktok(client))
