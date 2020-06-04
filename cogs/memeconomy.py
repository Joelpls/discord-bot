import asyncio
import os
import discord
from discord.ext import commands
import json
import pymongo
import random
import Slots
from num2words import num2words

import Utils


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

    @commands.command(aliases=['bal', 'bank', 'dosh', 'stash','BalanceEnglish','BalEng', 'BalWords'])
    async def balance(self, ctx, member: discord.Member = None):
        """
        Check the balance of your account or another member.
        'BalanceEnglish','BalEng', 'BalWords' returns the english representation of your balance.
        """
        member = member or ctx.author
        if member.bot:
            return
        guild = ctx.guild
        bank = db[str(ctx.guild.id)]

        account = bank.find_one({"user_id": member.id, "server": guild.id})
        amount = account.get('money')

        if account and ctx.invoked_with.lower() in ['balanceenglish','baleng', 'balwords']:
            amount_english = num2words(amount)
            await ctx.send(f"{member.display_name} has {amount_english} meme bucks.")
        elif account:
            await ctx.send(f"{member.display_name} has ${amount}.")
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

    @commands.command(aliases=['bals', 'monies', 'moneyrank', 'moneyranks'])
    async def balances(self, ctx):
        """Show the balances of all users"""
        bank = db[str(ctx.guild.id)]
        all_users = bank.find({}).sort('money', -1)

        user_bals = ''
        index = 1
        for doc in all_users:
            try:
                user = self.client.get_user(doc['user_id']).display_name
                s = f'**{index})** {user}: ${doc["money"]}\n'
                user_bals += s
            except KeyError:
                continue
            index += 1

        balances_embed = discord.Embed(title='Balances', description=user_bals, color=discord.Color(random.randint(1, 16777215)))
        await ctx.send(embed=balances_embed)

    @commands.command(aliases=['slot', 'slotmachine'])
    async def slots(self, ctx, bet=0):
        """
        Press your luck at the slot machine!
        Usage: !slots [bet]
        Payouts:
            2+ in a row.
            Stars are wild.
        """
        lines = 1  # TODO let the user choose the number of lines to play
        if bet <= 0:
            return

        # check have enough money
        guild = ctx.guild
        player = ctx.message.author
        bank = db[str(ctx.guild.id)]
        bulk_updates = []

        account = bank.find_one({"user_id": player.id, "server": guild.id})
        if account['money'] < bet:
            await ctx.send("Insufficient funds")
            return

        # subtract bet from account
        bulk_updates.append(pymongo.UpdateOne({"user_id": player.id, "server": guild.id},
                                              {"$inc": {"money": -1 * bet}}))

        bonus = Utils.Reel.STAR.value
        slots = list(e.value for e in Utils.Reel)
        wheels = [random.choice(slots), random.choice(slots), random.choice(slots), random.choice(slots), random.choice(slots)]
        msg = await ctx.send(f"| {wheels[0]} | {wheels[1]} | {wheels[2]} | {wheels[3]} | {wheels[4]} |")
        for i in range(0, 3):
            await asyncio.sleep(0.5)
            wheels = [random.choice(slots), random.choice(slots), random.choice(slots), random.choice(slots),
                      random.choice(slots)]
            await msg.edit(content=f"| {wheels[0]} | {wheels[1]} | {wheels[2]} | {wheels[3]} | {wheels[4]} |")

        slotM = Slots.SlotMachine(size=(5, lines), bonus=bonus)
        r = slotM()
        winnings = Slots.get_winnings(slotM.reel, slotM.checkLine(r[0]), bet, bonus)
        message = 'Lose'
        if winnings > 0:
            message = f'Win! ${winnings}'
        await asyncio.sleep(0.5)
        await msg.edit(content=f"| {r[0][0]} | {r[0][1]} | {r[0][2]} | {r[0][3]} | {r[0][4]} |")
        await asyncio.sleep(0.4)
        await msg.edit(content=f"| {r[0][0]} | {r[0][1]} | {r[0][2]} | {r[0][3]} | {r[0][4]} |\n"
                               f"{message}")

        # add winnings to account
        if winnings > 0:
            bulk_updates.append(pymongo.UpdateOne({"user_id": player.id, "server": guild.id},
                                                  {"$inc": {"money": winnings}}))
        bank.bulk_write(bulk_updates)


def setup(client):
    client.add_cog(Memeconomy(client))
