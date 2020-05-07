import discord
import json
import os
from discord.ext import commands, tasks
from itertools import cycle


def load_json(token):
    with open('./config.json') as f:
        config = json.load(f)
    return config.get(token)


client = commands.Bot(command_prefix=load_json('prefix'), case_insensitive=True)
for filename in os.listdir('./cogs'):
    if filename.endswith('.py'):
        client.load_extension(f'cogs.{filename[:-3]}')


@client.event
async def on_ready():
    # change_status.start()
    print('Bot is ready')


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
