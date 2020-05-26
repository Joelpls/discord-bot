import os

import discord
from discord.ext import commands
import json
from pymongo import MongoClient
import random
import datetime


def load_json(token):
    with open('./config.json') as f:
        config = json.load(f)
    return config.get(token)


cluster = MongoClient(os.environ.get('MONGODB_ADDRESS'))
db = cluster['Ranks']


class Ranks(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print('Ranks cog ready')

    @commands.command()
    async def level(self, ctx):
        """See your level"""
        try:
            name = ctx.message.mentions[0]
            if name.bot:
                return
            await get_user_level(ctx, name)
        except IndexError:
            await get_user_level(ctx, ctx.author)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        # Don't get XP for checking your level or rankings. It gets too confusing.
        string_list = ['!level', '!rank', '!ranks', '!ranking', '!rankings']
        if message.content in string_list:
            return

        database = db[str(message.guild.id)]

        player = message.author
        guild = message.guild
        utc_time = datetime.datetime.utcnow()

        # Get a bonus for using meme bot or uploading memes (any image)
        bonus = False
        try:
            image = message.attachments[0].url
            suffix_list = ['jpg', 'jpeg', 'png', 'gif', 'mp4']
            if image.casefold().endswith(tuple(suffix_list)):
                bonus = True
        except IndexError:
            pass
        if message.content.startswith(load_json('prefix')):
            bonus = True

        # Get the player's XP
        # 2% chance of getting 50, 1% for 100, 0.1% for 500, 0.01% for 1000
        xp_list = [1, 50, 100, 500, 1000]
        weights = [1, .02, .01, .001, .0001]
        xp = random.choices(xp_list, weights=weights, k=1)[0]

        if xp == 1:
            min_xp = 15
            max_xp = 30
            xp = random.randint(min_xp, max_xp)

        if bonus:
            xp = int(xp * 1.5)

        # Check cooldown time (gain XP only after cooldown time)
        cooldown_time = 30  # seconds
        doc = database.find_one({"user_id": player.id, "server": guild.id})
        if doc:
            doc_date = doc.get('date')
            diff = (utc_time - doc_date).total_seconds()
            if diff < cooldown_time:
                return

        database.find_one_and_update({"user_id": player.id, "server": guild.id},
                                     {"$inc": {"xp": xp, "messages": 1}, "$set": {"date": utc_time}}, upsert=True)
        database.create_index([("xp", -1)])
        database.create_index([("user_id", 1), ("server", 1)])

        if doc is None:
            return

        # check if they leveled up
        curr_level = get_level_from_xp(doc['xp'])
        new_level = get_level_from_xp(doc['xp'] + xp)
        if new_level != curr_level:
            await message.channel.send(f'{player.display_name} is now level {new_level}!')

    @commands.command(aliases=['ranks', 'ranking', 'rankings'])
    async def rank(self, ctx):
        """Shows the ranks of the server's users."""
        database = db[str(ctx.guild.id)]
        all_users = database.find({}).sort('xp', -1)

        rank = ''
        index = 1
        for doc in all_users:
            try:
                user = self.client.get_user(doc['user_id'])
                s = f'**{index})** {user.display_name}: {doc["xp"]} XP | Level: {get_level_from_xp(doc["xp"])}\n'
                rank += s
            except KeyError:
                continue
            index += 1

        rank_embed = discord.Embed(title='Rank', description=rank, color=discord.Color(random.randint(1, 16777215)))
        await ctx.send(embed=rank_embed)


async def get_user_level(ctx, name):
    player = name
    guild = ctx.guild

    database = db[str(ctx.guild.id)]
    doc = database.find_one({"user_id": player.id, "server": guild.id})

    if not doc:
        await ctx.send(f"{player.display_name} is level 0.\n")
        return

    level = get_level_from_xp(doc['xp'])

    # Get the rank by counting the users with XP greater than this user
    rank = database.count({'xp': {'$gt': doc['xp']}}) + 1

    next_lvl_xp = get_level_xp(level)
    curr_lvl_xp = next_lvl_xp - get_level_progress(doc['xp'])

    description = (f"Total XP: {doc['xp']}\n"
                   f"{curr_lvl_xp}/{next_lvl_xp} XP\n"
                   f"{print_progress_bar(iteration=curr_lvl_xp, total=next_lvl_xp, length=30)}")

    color = get_color(rank)

    level_embed = discord.Embed(title=f"{player.display_name} | Level {level} | Rank #{rank}", description=description,
                                color=color)
    level_embed.set_thumbnail(url=player.avatar_url)
    await ctx.send(embed=level_embed)


# Print iterations progress
def print_progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=100, fill='█'):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    return '%s |%s| %s%% %s' % (prefix, bar, percent, suffix)


def get_level_xp(lvl: int):
    return (4 * (lvl ** 2)) + (40 * lvl) + 100


def get_level_from_xp(xp) -> int:
    remaining_xp = xp
    level = 0
    while remaining_xp >= get_level_xp(level):
        remaining_xp -= get_level_xp(level)
        level += 1
    return level


def get_level_progress(xp):
    remaining_xp = xp
    level = 0
    while remaining_xp >= get_level_xp(level):
        remaining_xp -= get_level_xp(level)
        level += 1
    return get_level_xp(level) - remaining_xp


def get_color(rank):
    """
    Get the color for rank 1, 2, or 3.
    Gold, Silver, or Bronze.
    If higher than rank 3, get a random color.
    """
    if rank == 1:
        color = int(0xffd700)
    elif rank == 2:
        color = int(0xc0c0c0)
    elif rank == 3:
        color = int(0xcd7f32)
    else:
        color = random.randint(1, 16777215)

    return discord.Color(color)


def setup(client):
    client.add_cog(Ranks(client))
