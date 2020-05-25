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


cluster = MongoClient(load_json('db_address'))
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
        if message.author.id == load_json('bot_id') or message.author.bot:
            return

        database = db[str(message.guild.id)]

        player = message.author
        guild = message.guild
        utc_time = datetime.datetime.utcnow()

        # Get the player's XP
        # 2% chance of getting 50, 1% for 100, 0.1% for 500, 0.01% for 1000
        xp_list = [1, 50, 100, 500, 1000]
        weights = [1, .02, .01, .001, .0001]
        xp = random.choices(xp_list, weights=weights, k=1)[0]

        if xp == 1:
            min_xp = 15
            max_xp = 30
            xp = random.randint(min_xp, max_xp)

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
        if doc is None:
            return

        # check if they leveled up
        curr_level = get_level_from_xp(doc['xp'])
        new_level = get_level_from_xp(doc['xp'] + xp)
        if new_level != curr_level:
            await message.channel.send(f'{player.display_name} is now level {new_level}!')

    @commands.command(aliases=['ranks'])
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

        rank_embed = discord.Embed(title='Rank', description=rank, color=0x9f21ff)
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

    # TODO make this look cool
    await ctx.send(f"{player.display_name} is level {level}.\n"
                   f"Total XP: {doc['xp']}\n"
                   f"{get_level_progress(doc['xp'])} XP needed to rank up.")


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


def setup(client):
    client.add_cog(Ranks(client))
