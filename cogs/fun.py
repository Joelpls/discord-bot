import random

import discord
from discord.ext import commands

import Utils


class Fun(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print('Fun cog ready')

    @commands.command(aliases=['dice', 'r'])
    async def roll(self, ctx, user_roll):
        """Roll some dice!"""
        user_roll = user_roll.split('d')

        if len(user_roll) != 2:
            await ctx.send('usage: XdY where X is the number of dice and Y is the number of sides')
            return

        try:
            dice = int(user_roll[0])
            sides = int(user_roll[1])
        except ValueError:
            await ctx.send('usage: XdY where X is the number of dice and Y is the number of sides')
            return

        if sides < 1 or sides > 10000 or dice > 100 or dice < 1:
            await ctx.send('Limit of 100 dice and 10000 sides')
            return

        rolls = []
        total = 0
        for d in range(0, dice):
            rolled = random.randint(1, sides)
            rolls.append(rolled)
            total += rolled

        await ctx.send(f'{ctx.author.display_name} rolled: {rolls} for **{total}**')

    @commands.command(name='8ball', aliases=['8-Ball'])
    async def _8ball(self, ctx, *, question):
        """Ask the Magic 8-Ball a question!"""
        responses = Utils.load_json('8ball_responses')
        await ctx.send(f' {ctx.author.display_name}\'s question: {question}\nAnswer: {random.choice(responses)}')

    @commands.command(hidden=True)
    async def ban(self, ctx, name):
        await ctx.send(f'Shut up, {name.title()}')

    @commands.command(aliases=['em', 'me'])
    async def emote(self, ctx, *, text):
        """Post an action as your name, e.g. !emote waves hello"""
        await ctx.message.delete()
        user_name = ctx.author.display_name
        message = f'_{user_name} {text}_'
        await ctx.send(message)

    @commands.command(aliases=['respects', 'payrespect', 'respect', 'payrespects'])
    async def f(self, ctx, *, respectee=None):
        """Press f to pay respects"""
        await ctx.message.delete()
        user_name = ctx.author.display_name
        if respectee is None:
            message = f'_{user_name} pays respects_'
        else:
            message = f'_{user_name} pays respects to {respectee}_'
        await ctx.send(message)

    @commands.command(aliases=['greentext'])
    async def gt(self, ctx, *, text):
        """Post a greentext message"""
        text = f"```css\n{ctx.message.author.display_name}: >{text}\n```"
        await ctx.send(f'{text}')
        await ctx.message.delete()

    @commands.command()
    async def blink(self, ctx):
        """Post the blinking guy gif"""
        await ctx.message.delete()
        await ctx.send(f"{ctx.message.author.display_name}:", file=discord.File("blinking_guy.gif"))


async def setup(client):
    await client.add_cog(Fun(client))