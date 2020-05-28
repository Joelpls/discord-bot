import os
import discord
from discord.ext import commands
import json
import praw
import prawcore
import random


def load_json(token):
    with open('./config.json') as f:
        config = json.load(f)
    return config.get(token)


reddit = praw.Reddit(client_id=os.environ.get('REDDIT_CLIENT_ID'),
                     client_secret=os.environ.get('REDDIT_CLIENT_SECRET'),
                     user_agent="meme bot for Discord by Joel")


class Memes(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print('Memes cog ready')

    @commands.command(aliases=['dankmeme', 'memes', 'dankmemes'])
    async def meme(self, ctx, *args):
        """
        Get a random meme
        Usage: !meme <subreddit> (optional) <# of submissions> (optional)
        Default subreddit is /r/dankmemes
        Number of submissions argument determines how many of the top posts to pick a random post from. Limit 200.
        Posts are the top of the past week.
        """
        limit = 200
        subreddit = "dankmemes"

        # Get the subreddit and limit
        if len(args) > 0:
            if args[0].isnumeric():
                limit = int(args[0])
                if len(args) > 1 and args[1].isalpha() or args[1].isalnum():
                    subreddit = args[1]
            elif args[0].isalpha() or args[0].isalnum():
                subreddit = args[0]
                if len(args) > 1 and args[1].isnumeric():
                    limit = int(args[1])

        if limit > 200:
            limit = 200

        try:
            dankmemes = [post for post in reddit.subreddit(subreddit).top(time_filter='week', limit=limit)]
            meme = random.choice(dankmemes)
        except prawcore.Redirect:
            await ctx.send("Error retrieving subreddit")
            return
        except prawcore.NotFound:
            await ctx.send("Subreddit not found. Is it private or banned?")
            return

        # Filter out NSFW memes
        index = 0
        while index < 20 and meme.over_18:
            meme = random.choice(dankmemes)
            index += 1
        if meme.over_18:
            await ctx.send("Is that subreddit appropriate?")
            return

        meme_embed = discord.Embed(title=meme.title[0:255],
                                   description=f'{meme.ups:,} ⬆️',
                                   url=f'https://www.reddit.com{meme.permalink}',
                                   color=random.randint(1, 16777215))
        meme_embed.set_image(url=meme.url)
        meme_embed.set_footer(text=meme.subreddit_name_prefixed)

        await ctx.send(embed=meme_embed)


def setup(client):
    client.add_cog(Memes(client))
