import discord
import random
import json
import os
from discord.ext import commands, tasks
from itertools import cycle
from pymongo import MongoClient
import re


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


cluster = MongoClient(load_json('db_address'))
react_db = cluster['Reactions']

client = commands.Bot(command_prefix=load_json('prefix'), case_insensitive=True)
for filename in os.listdir('./cogs'):
    if filename.endswith('.py'):
        client.load_extension(f'cogs.{filename[:-3]}')


@client.event
async def on_ready():
    # change_status.start()
    print('Bot is ready')


@client.command(aliases=['dice', 'r'])
async def roll(ctx, user_roll):
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


@client.command(name='8ball', aliases=['8-Ball'])
async def _8ball(ctx, *, question):
    """Ask the Magic 8-Ball a question!"""
    responses = load_json('8ball_responses')
    await ctx.send(f' {ctx.author.display_name}\'s question: {question}\nAnswer: {random.choice(responses)}')


@client.event
async def on_reaction_add(reaction, user):
    # Skip if this is their own message or a bot message
    if user != reaction.message.author and client.user != reaction.message.author:
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


@client.event
async def on_reaction_remove(reaction, user):
    if user != reaction.message.author and client.user != reaction.message.author:
        collection = react_db[str(user.guild.id)]

        # Remove a reaction received by the message author
        if collection.count_documents({"user": reaction.message.author.id}, limit=1) != 0:
            collection.update_one({"user": reaction.message.author.id}, {"$inc": {"reaction_received": -1}})

        # Remove a reaction given by the reactor
        if collection.count_documents({"user": user.id}, limit=1) != 0:
            collection.update_one({"user": user.id}, {"$inc": {"reaction_given": -1}})


@client.command()
async def reactions(ctx):
    """Shows the total number of reactions each user has received on their messages"""
    collection = react_db[str(ctx.guild.id)]
    all_users = collection.find({}).sort('reaction_received', -1)

    received = ''
    index = 1
    for doc in all_users:
        try:
            user = client.get_user(doc['user'])
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
            user = client.get_user(doc['user'])
            s = f'**{index})** {user.display_name}: {doc["reaction_given"]}\n'
            given += s
        except KeyError:
            continue
        index += 1

    embed = discord.Embed(color=0x00ff00).add_field(name='**Total reactions received:**', value=received, inline=True) \
        .add_field(name='**Total reactions given:**', value=given, inline=True)

    await ctx.send(embed=embed)


@client.command(hidden=True)
async def ban(ctx, name):
    await ctx.send(f'Shut up, {name.title()}')


@client.command(aliases=['em', 'me'])
async def emote(ctx, *, text):
    await ctx.message.delete()
    user_name = ctx.author.display_name
    message = f'_{user_name} {text}_'
    await ctx.send(message)


@client.event
async def on_message(message):
    """remove mobile links"""
    if not message.author.bot:
        # Check to see if the user is Alex
        if message.author.id == 224648266472620032:
            # Check to see if he just posted some bullshit tiktok garbage
            tik_tok_links = re.findall(pattern=r"tiktok\.com", string=message.content, flags=(re.M | re.I))
            if tik_tok_links:
                await message.channel.send("Alex, Tik Tok is bad and you should feel bad. Stop posting Tik Tok links!")

        pattern = re.compile(r'(?<=https://m\.)([^\s]+)')
        matches = re.findall(pattern, message.content)
        if len(matches) > 0:
            mobile_links = ""
            for match in matches:
                mobile_links += f'https://{match} '

            await message.channel.send(mobile_links.strip())
        else:
            await client.process_commands(message)
    else:
        await client.process_commands(message)


status = cycle(load_json('statuses'))


@tasks.loop(minutes=load_json('loop_time'))
async def change_status():
    await client.change_presence(activity=discord.Game(next(status)))


@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        return await ctx.send('Please pass in all required arguments.')
    if isinstance(error, commands.CommandNotFound):
        if ctx.invoked_with.startswith('!'):
            return
        return await ctx.send('Invalid Command')
    if isinstance(error, commands.BadArgument):
        if ctx.command.qualified_name == 'discover':
            return await ctx.send('Argument must be a digit.')
        else:
            return await ctx.send('Try again')


client.run(load_json('token'))
