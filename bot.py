import discord
from discord import Intents
import json
import os
import datetime
from discord.ext import commands, tasks
from itertools import cycle
from pymongo import MongoClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

intents = Intents.all()


def load_json(token):
    with open('./config.json') as f:
        config = json.load(f)
    return config.get(token)


scheduler = AsyncIOScheduler()

cluster = MongoClient(os.environ.get('MONGODB_ADDRESS'))
db = cluster['Logs']

client = commands.Bot(command_prefix=load_json('prefix'), case_insensitive=True)
for filename in os.listdir('./cogs'):
    if filename.endswith('.py'):
        client.load_extension(f'cogs.{filename[:-3]}')


async def send_free_game_message():
    channels = [751131240203026566, 688900848956342324]  # TODO get channel names from database
    for ch in channels:
        channel = client.get_channel(ch)
        await channel.send('https://www.epicgames.com/store/en-US/free-games')


async def send_contests():
    channel = client.get_channel(688901859628548189)
    await channel.send('https://disneyremysratatouilleadventuresweepstakes.com/')


@client.event
async def on_ready():
    # change_status.start()
    scheduler.start()
    scheduler.add_job(send_free_game_message, CronTrigger(day_of_week='thu', hour=11, timezone='US/Eastern'))
    scheduler.add_job(send_contests, CronTrigger(hour=11, minute=30, timezone='US/Eastern'))
    print('Bot is ready')


@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        print_log('MissingRequiredArgument error', ctx)
        return await ctx.send('Please pass in all required arguments.')

    if isinstance(error, commands.CommandNotFound):
        print_log('CommandNotFound error', ctx)

    if isinstance(error, commands.BadArgument):
        print_log('BadArgument error', ctx)
        if ctx.command.qualified_name == 'discover':
            return await ctx.send('Argument must be a digit.')
        if ctx.command.qualified_name == 'pay':
            return await ctx.send('Usage: !pay <amount> <@member>')
        if ctx.command.qualified_name == 'deposit':
            return await ctx.send('Usage: !deposit <amount> <@member>')
        if ctx.command.qualified_name == 'slots':
            return await ctx.send('Usage: !slots [bet]')

        return await ctx.send('Try again')

    print_log(str(error), ctx)


@client.command(name='logs', aliases=['errors', 'errorlogs'])
async def error_logs(ctx, num_logs=5):
    """Print out the latest error log messages. Defaults to 5. Limit 25."""
    collection = db[str(ctx.guild.id)]
    if num_logs > 25:
        num_logs = 25

    # Get logs of mentioned user only
    if len(ctx.message.mentions) > 0:
        username = str(ctx.message.mentions[0])
        logs = collection.find({'user_name': username}).limit(num_logs).sort('_id', -1)
    else:
        logs = collection.find({}).limit(num_logs).sort('_id', -1)

    msg_list = []
    for log in logs:
        message = f'<{log.get("date")} UTC> {log.get("error")} - {log.get("user_name")} : {log.get("message_content")}'
        msg_list.append(f'{message}\n')

    await ctx.send(''.join(msg_list))


def print_log(error_name: str, ctx):
    collection = db[str(ctx.guild.id)]
    log_message = f"{error_name} - {ctx.message.author} : {ctx.message.content}"
    utc_time = datetime.datetime.utcnow()

    db_log_post = {'date': utc_time, 'error': error_name, 'user_name': str(ctx.message.author), 'message_content': ctx.message.content,
                   'user_id': ctx.author.id, 'channel': ctx.message.channel.id, 'message_id': ctx.message.id}
    collection.insert_one(db_log_post)

    print(f'{utc_time} UTC: {log_message}')


client.run(os.environ.get('DISCORD_TOKEN'))
