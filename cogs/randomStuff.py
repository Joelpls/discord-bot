import os

import discord
import json
from discord.ext import commands
from pymongo import MongoClient
import re
import random


def load_json(token):
    with open('./config.json') as f:
        config = json.load(f)
    return config.get(token)


async def create_indices(collection):
    collection.create_index([("user", 1)])
    collection.create_index([("reaction_received", -1)])
    collection.create_index([("reaction_given", -1)])
    collection.create_index([("user", 1), ("reaction_received", -1)])
    collection.create_index([("user", 1), ("reaction_given", -1)])


cluster = MongoClient(os.environ.get('MONGODB_ADDRESS'))
react_db = cluster['Reactions']


class RandomStuff(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print('Random cog ready')

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
        responses = load_json('8ball_responses')
        await ctx.send(f' {ctx.author.display_name}\'s question: {question}\nAnswer: {random.choice(responses)}')

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        # Skip if this is their own message or a bot message
        if user != reaction.message.author and self.client.user != reaction.message.author:
            collection = react_db[str(user.guild.id)]
            await create_indices(collection)

            # Update the number of reactions received by the message author
            if collection.count_documents({"user": reaction.message.author.id}, limit=1) == 0:
                collection.insert_one({"user": reaction.message.author.id, "reaction_received": 1})
            elif collection.count_documents({"user": reaction.message.author.id}, limit=1) > 0:
                collection.update_one({"user": reaction.message.author.id}, {"$inc": {"reaction_received": 1}})

            # Update the number of reactions given out by the reactor
            if collection.count_documents({"user": user.id}, limit=1) == 0:
                collection.insert_one({"user": user.id, "reaction_given": 1})
            elif collection.count_documents({"user": user.id}, limit=1) > 0:
                collection.update_one({"user": user.id}, {"$inc": {"reaction_given": 1}})

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        if user != reaction.message.author and self.client.user != reaction.message.author:
            collection = react_db[str(user.guild.id)]

            # Remove a reaction received by the message author
            if collection.count_documents({"user": reaction.message.author.id}, limit=1) != 0:
                collection.update_one({"user": reaction.message.author.id}, {"$inc": {"reaction_received": -1}})

            # Remove a reaction given by the reactor
            if collection.count_documents({"user": user.id}, limit=1) != 0:
                collection.update_one({"user": user.id}, {"$inc": {"reaction_given": -1}})

    @commands.command()
    async def reactions(self, ctx):
        """Shows the total number of reactions each user has received on their messages"""
        collection = react_db[str(ctx.guild.id)]
        all_users = collection.find({}).sort('reaction_received', -1)

        received = ''
        index = 1
        for doc in all_users:
            try:
                user = self.client.get_user(doc['user'])
                s = f'**{index})** {user.display_name}: {doc["reaction_received"]}\n'
                received += s
            except KeyError:
                continue
            index += 1
        index = 1

        given = ''
        all_users2 = collection.find({}).sort('reaction_given', -1)
        for doc in all_users2:
            try:
                user = self.client.get_user(doc['user'])
                s = f'**{index})** {user.display_name}: {doc["reaction_given"]}\n'
                given += s
            except KeyError:
                continue
            index += 1

        embed = discord.Embed(title='Reaction Totals',
                              description='Number of reactions users have received on their messages or given to other users.',
                              color=0x00ff00)
        embed.add_field(name='Total reactions received:', value=received, inline=True)
        embed.add_field(name='Total reactions given:', value=given, inline=True)

        await ctx.send(embed=embed)

    @commands.command(hidden=True)
    async def ban(self, ctx, name):
        await ctx.send(f'Shut up, {name.title()}')

    @commands.command(name='freegames', aliases=['freegame'])
    async def free_games(self, ctx):
        """Show this week's free games from the Epic Store"""
        # I should use beautiful soup library to parse this but for now I'm lazy
        await ctx.send('https://www.epicgames.com/store/en-US/free-games')

    @commands.command(aliases=['em', 'me'])
    async def emote(self, ctx, *, text):
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

    @commands.Cog.listener()
    async def on_message(self, message):
        """remove mobile links"""
        if not message.author.bot:
            '''
            # Check to see if the user is Alex
            if message.author.id == 224648266472620032:
                # Check to see if he just posted some bullshit tiktok garbage
                tik_tok_links = re.findall(pattern=r"tiktok\.com", string=message.content, flags=(re.M | re.I))
                if tik_tok_links:
                    await message.channel.send("Alex, Tik Tok is bad and you should feel bad. Stop posting Tik Tok links!")
            '''
            # Fina all 'm.' links and don't include the '?sfnsn' at the end
            matches = re.findall(r'(?<=https://m\.(?!tiktok))\S*?(?=sfnsn|$)', message.content, re.MULTILINE)
            matches = list(dict.fromkeys(matches))  # Remove duplicates
            if len(matches) > 0:
                mobile_links = ""
                for match in matches:
                    mobile_links += f'https://{match}\n'

                await message.channel.send(mobile_links.strip())

    @commands.command(aliases=['greentext'])
    async def gt(self, ctx, *, text):
        text = f"```css\n{ctx.message.author.display_name}: >{text}\n```"
        await ctx.send(f'{text}')
        await ctx.message.delete()


def setup(client):
    client.add_cog(RandomStuff(client))
