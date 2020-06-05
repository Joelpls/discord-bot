import os
import discord
from discord.ext import commands
from pymongo import MongoClient
import json
import praw
import prawcore
import random
import re


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
    async def meme(self, ctx, *args):
        """
        Get a random meme
        Usage: !meme <subreddit> <# of submissions> (optional arguments)
        Default subreddit is /r/wholesomememes
        Number of submissions argument determines how many of the top posts to pick a random post from. Limit 300, Default 50.
        Posts are the top of the past week.
        """
        default_limit = 50
        max_limit = 300

        limit = default_limit
        subreddit = "wholesomememes"

        # Get the subreddit and limit
        if len(args) > 0:
            if args[0].isnumeric():
                limit = int(args[0])
                if len(args) > 1 and re.match(r'^\w+$', args[1]):
                    subreddit = args[1]
            elif re.match(r'^\w+$', args[0]):
                subreddit = args[0]
                if len(args) > 1 and args[1].isnumeric():
                    limit = int(args[1])

        if limit > max_limit:
            limit = default_limit

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
