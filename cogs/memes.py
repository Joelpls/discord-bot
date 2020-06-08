import os
import discord
from discord.ext import commands
from pymongo import MongoClient
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

cluster = MongoClient(os.environ.get('MONGODB_ADDRESS'))
db = cluster['Memes']


class Memes(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print('Memes cog ready')

    @commands.command(aliases=['wholesomememe', 'memes', 'wholesomememes'])
    async def meme(self, ctx, subreddit: str = 'wholesomememes', timeline: str = 'week', limit = '50'):
        """
        Get a random meme
        Usage: !meme <subreddit> <time filter> <# of submissions> (optional arguments)
        Default subreddit is /r/wholesomememes
        Time filter is either hour, day, week, month, year, or all. Default: week.
        Number of submissions argument determines how many of the top posts to pick a random post from. Limit 300, Default 50.
        Posts are the top of the past week.
        """
        default_limit = 50
        max_limit = 300

        if timeline.isnumeric():
            temp = limit
            limit = int(timeline)
            timeline = str(temp)
            # Still numeric. They didn't pass in a timeline.
            if timeline.isnumeric():
                timeline = 'week'

        timeline = timeline.lower()
        if timeline in ['hour', 'hourly', '1', '1h', '1hour']:
            time_filter = 'hour'
        elif timeline in ['day', 'daily', '24', '24h', '24hours']:
            time_filter = 'day'
        elif timeline in ['week', 'weekly', '7', '7d', '7days']:
            time_filter = 'week'
        elif timeline in ['month', 'monthly']:
            time_filter = 'month'
        elif timeline in ['year', 'yearly', '365', '365d', '365days']:
            time_filter = 'year'
        elif timeline in ['all', 'alltime', 'everything']:
            time_filter = 'all'
        else:
            await ctx.send('!meme <subreddit> <time filter> <# of submissions>\n'
                           'Time filter is either hour, day, week, month, year, or all. Default: week.')
            return

        limit = int(limit)
        if limit > max_limit:
            limit = default_limit

        try:
            dankmemes = [post for post in reddit.subreddit(subreddit).top(time_filter=time_filter, limit=limit)]
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

        message = await ctx.send(embed=meme_embed)

        collection = db[str(ctx.guild.id)]
        collection.insert_one({"message_id": message.id, "op": ctx.message.author.id})

        await message.add_reaction('⬆️')
        await message.add_reaction('⬇️')
        await message.add_reaction('🗑️')

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """
        The original poster can delete their message with the trashcan emoji.
        The message will automatically be deleted if 3 people down vote it.
        """
        collection = db[str(user.guild.id)]

        # If 3 people downvote this, delete it.
        if str(reaction) == '⬇️' and reaction.count >= 4:
            collection.delete_one({"message_id": reaction.message.id, "op": user.id})
            await reaction.message.delete()
            return

        # The original poster can trash their message.
        if not user.bot and reaction.message.author.bot:
            document = collection.find_one({"message_id": reaction.message.id, "op": user.id})
            if document is None:
                return

            if str(reaction) == '🗑️':
                collection.delete_one({"message_id": reaction.message.id, "op": user.id})
                await reaction.message.delete()
                return


def setup(client):
    client.add_cog(Memes(client))
