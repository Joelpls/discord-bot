import os
import discord
from discord.ext import commands
import json
import pymongo
import random
import datetime


def load_json(token):
    with open('./config.json') as f:
        config = json.load(f)
    return config.get(token)


cluster = pymongo.MongoClient(os.environ.get('MONGODB_ADDRESS'))
db = cluster['Ranks']


class Ranks(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print('Ranks cog ready')

    @commands.command()
    async def level(self, ctx, member: discord.Member = None):
        """See your level or another member's"""
        member = member or ctx.author
        if member.bot:
            return
        await get_user_level(ctx, member)

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

        # Check cooldown time (gain XP only after cooldown time)
        cooldown_time = 30  # seconds
        doc = database.find_one({"user_id": player.id, "server": guild.id})
        utc_time = datetime.datetime.utcnow()

        if doc:
            doc_date = doc.get('date')
            diff = (utc_time - doc_date).total_seconds()
            if diff < cooldown_time:
                return

        # Get a bonus for using meme bot or uploading memes (any image)
        bonus = check_bonus(message)

        # Get the player's XP
        # 2% chance of getting 50, 1% for 100, 0.1% for 500, 0.01% for 1000
        xp = get_xp(bonus)
        if xp >= 500:
            await message.channel.send(f"{xp} point message!")

        database.find_one_and_update({"user_id": player.id, "server": guild.id},
                                     {"$inc": {"xp": xp, "messages": 1}, "$set": {"date": utc_time}}, upsert=True)
        database.create_index([("xp", -1)])
        database.create_index([("user_id", 1), ("server", 1)])

        if doc is None:
            return

        # check if they leveled up
        await check_level_up(doc['xp'], message, player, xp)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.id == reaction.message.author.id or reaction.message.author.bot:
            return

        database = db[str(reaction.message.guild.id)]
        guild = reaction.message.guild

        # Check cooldown time (gain XP only after cooldown time)
        cooldown_time = 3  # seconds
        doc = database.find_one({"user_id": user.id, "server": guild.id})
        receiver_doc = database.find_one({"user_id": reaction.message.author.id, "server": guild.id})
        utc_time = datetime.datetime.utcnow()

        if doc:
            doc_date = doc.get('date_reaction')
            if doc_date:
                diff = (utc_time - doc_date).total_seconds()
                if diff < cooldown_time:
                    return

        # Give the person who reacted XP
        # Give the receiver of the reaction XP too
        xp_gained = 2
        bulk_updates = [pymongo.UpdateOne({"user_id": user.id, "server": guild.id},
                                          {"$inc": {"xp": xp_gained, "reactions": 1},
                                           "$set": {"date_reaction": utc_time}}, upsert=True),
                        pymongo.UpdateOne({"user_id": reaction.message.author.id, "server": guild.id},
                                          {"$inc": {"xp": xp_gained, "reactions": 1},
                                           "$set": {"date_reaction": utc_time}}, upsert=True)]
        database.bulk_write(bulk_updates)

        if doc is not None:
            # check if they leveled up
            await check_level_up(doc['xp'], reaction.message, user, xp_gained)

        if receiver_doc is not None:
            # check if receiver leveled up
            await check_level_up(receiver_doc['xp'], reaction.message, reaction.message.author, xp_gained)

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        if user.id == reaction.message.author.id or reaction.message.author.bot:
            return

        database = db[str(reaction.message.guild.id)]
        guild = reaction.message.guild

        # Remove XP from the person who reacted
        # Remove XP from the receiver of the reaction too
        xp_lost = -2
        bulk_updates = [pymongo.UpdateOne({"user_id": user.id, "server": guild.id},
                                          {"$inc": {"xp": xp_lost, "reactions": -1}}, upsert=True),
                        pymongo.UpdateOne({"user_id": reaction.message.author.id, "server": guild.id},
                                          {"$inc": {"xp": xp_lost, "reactions": -1}}, upsert=True)]
        database.bulk_write(bulk_updates)

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
    return '%s %s %s%% %s' % (prefix, bar, percent, suffix)


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


def check_bonus(message):
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
    return bonus


def get_xp(bonus):
    xp_list = [1, 50, 100, 500, 1000]
    weights = [1, .02, .01, .001, .0001]
    xp = random.choices(xp_list, weights=weights, k=1)[0]
    if xp == 1:
        min_xp = 15
        max_xp = 30
        xp = random.randint(min_xp, max_xp)
    if bonus:
        xp = int(xp * 1.5)
    return xp


async def check_level_up(curr_xp, message, player, xp_gained):
    curr_level = get_level_from_xp(curr_xp)
    new_level = get_level_from_xp(curr_xp + xp_gained)
    if new_level != curr_level:
        await message.channel.send(f'{player.display_name} is now level {new_level}!')


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
