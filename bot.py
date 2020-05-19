import discord
import json
import os
import datetime
import time
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
        print_log('MissingRequiredArgument', ctx)
        return await ctx.send('Please pass in all required arguments.')

    if isinstance(error, commands.CommandNotFound):
        print_log('CommandNotFound', ctx)

    if isinstance(error, commands.BadArgument):
        print_log('BadArgument', ctx)
        if ctx.command.qualified_name == 'discover':
            return await ctx.send('Argument must be a digit.')
        else:
            return await ctx.send('Try again')


def print_log(error_name: str, ctx):
    ts = time.time()
    st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    log_message = f"<{st}> - {error_name} error - {ctx.message.author} : {ctx.message.content}"

    print(log_message)
    with open("error_logs.txt", "a") as log_file:
        print(log_message, file=log_file)


client.run(load_json('token'))
