import asyncio
import os
import discord
from discord.ext import commands
import json
import pymongo
import random


def load_json(token):
    with open('./config.json') as f:
        config = json.load(f)
    return config.get(token)


def is_owner_or_approved():
    async def predicate(ctx):
        guild = ctx.guild
        if ctx.author is guild.owner:
            return True
        if ctx.author.id == 413139799453597698:
            return True

    return commands.check(predicate)


cluster = pymongo.MongoClient(os.environ.get('MONGODB_ADDRESS'))
db = cluster['Economy']


class Memeconomy(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print('Memeconomy cog ready')

    @commands.guild_only()
    @is_owner_or_approved()
    @commands.command(hidden=True)
    async def giveall(self, ctx, amount):
        members = ctx.guild.members
        for member in members:
            await self.deposit(ctx, amount, member)

    @commands.guild_only()
    @is_owner_or_approved()
    @commands.command(aliases=["add", "give"])
    async def deposit(self, ctx, amount, member: discord.Member = None):
        """
        Deposit into a member's account.
        Usage: !deposit <amount> <@member>
        """
        if type(amount) is str:
            try:
                amount = int(round(float(amount.strip('$'))))
            except ValueError:
                await ctx.send("Usage: deposit <amount> <@member>")
                return

        member = member or ctx.author
        if member.bot:
            return

        guild = ctx.guild
        bank = db[str(ctx.guild.id)]

        account = bank.find_one({"user_id": member.id, "server": guild.id})
        # Don't go negative
        if amount < 0 and int(account.get('money')) - abs(amount) < 0:
            amount = -1 * account.get('money')
            bank.update_one({"user_id": member.id, "server": guild.id},
                            {"$set": {"money": 0}}, upsert=True)
        else:
            bank.update_one({"user_id": member.id, "server": guild.id},
                            {"$inc": {"money": amount}}, upsert=True)

        give_take = 'given to'
        if amount < 0:
            give_take = 'taken from'
        await ctx.send(f"${amount} has been {give_take} {member.mention}.")

    @commands.command(aliases=['bal', 'bank', 'dosh', 'stash'])
    async def balance(self, ctx, member: discord.Member = None):
        """Check the balance of your account or another member"""
        member = member or ctx.author
        if member.bot:
            return
        guild = ctx.guild
        bank = db[str(ctx.guild.id)]

        account = bank.find_one({"user_id": member.id, "server": guild.id})

        if account:
            await ctx.send(f"{member.display_name} has ${account.get('money')}.")
        else:
            await ctx.send(f"{member.display_name} has no money.")

    @commands.command()
    async def pay(self, ctx, amount, recipient: discord.Member = None):
        """
        Pay another member.
        Usage: !pay <amount> <@member>
        """
        if type(amount) is str:
            try:
                amount = int(round(float(amount.strip('$'))))
            except ValueError:
                await ctx.send("Please pass an integer")
                return

        if recipient is None:
            await ctx.send("Usage: !pay <amount> <@member>")
            return
        payer = ctx.author
        if recipient is not None and recipient is payer:
            await ctx.send("You can't pay yourself.")
            return
        if recipient.bot:
            await ctx.send("You can't pay bots.")
            return

        guild = ctx.guild
        bank = db[str(ctx.guild.id)]
        payer_account = bank.find_one({"user_id": payer.id, "server": guild.id})
        if payer_account is None:
            await ctx.send("You do not have an account with us.")
            return

        if payer_account.get('money') < amount:
            await ctx.send("Insufficient funds")
            return

        # Subtract from payer
        bank.update_one({"user_id": payer.id, "server": guild.id},
                        {"$inc": {"money": -1 * amount}}, upsert=True)
        # Add to recipient
        bank.update_one({"user_id": recipient.id, "server": guild.id},
                        {"$inc": {"money": amount}}, upsert=True)

        await ctx.send(f"{payer.display_name} paid {recipient.display_name} ${amount}")

    @commands.command()
    async def slots(self, ctx, bet=0):
        # TODO check have enough money
        # TODO subtract bet from account
        # [ Gem, Cherry, Banana, Lemon, Strawberry, Bar]
        gem = "\U0001F48E"
        cherry = "\U0001F352"
        banana = "\U0001F34C"
        lemon = "\U0001F34B"
        strawberry = "\U0001F353"
        bar = "\U0001F36B"
        slots = [gem, cherry, banana, lemon, strawberry, bar]
        results = [random.choice(slots), random.choice(slots), random.choice(slots)]

        wheels = [random.choice(slots), random.choice(slots), random.choice(slots)]
        msg = await ctx.send(f"| {wheels[0]} | {wheels[1]} | {wheels[2]} |")
        for i in range(0, 3):
            await asyncio.sleep(0.5)
            wheels = [random.choice(slots), random.choice(slots), random.choice(slots)]
            await msg.edit(content=f"| {wheels[0]} | {wheels[1]} | {wheels[2]} |")

        await asyncio.sleep(0.5)
        await msg.edit(content=f"| {results[0]} | {results[1]} | {results[2]} |")
        await asyncio.sleep(0.4)
        await msg.edit(content=f"| {results[0]} | {results[1]} | {results[2]} |\n"
                               f"{check_win(results, bet)}")
        # TODO add winnings to account


def check_win(win_list: [], bet):
    first = win_list[0]
    second = win_list[1]
    third = win_list[2]

    if first == second and second == third:
        return "Win"

    if first == second:
        return "Win"

    else:
        return "Lose"


def setup(client):
    client.add_cog(Memeconomy(client))
