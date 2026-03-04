import datetime
import os

import discord
from discord import Intents
from discord.ext import commands
from pymongo import MongoClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import Utils

intents = Intents.all()


scheduler = AsyncIOScheduler()

cluster = MongoClient(os.environ.get('MONGODB_ADDRESS'), serverSelectionTimeoutMS=1000)
logs_db = cluster['Logs']


class Bot(commands.Bot):
    async def setup_hook(self):
        excluded_files = ['discover.py', 'memes.py']
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and filename not in excluded_files:
                await self.load_extension(f'cogs.{filename[:-3]}')

        await self.tree.sync()

        scheduler.start()
        scheduler.add_job(send_free_game_message, CronTrigger(day_of_week='thu', hour=11, minute=3, jitter=180, timezone='America/New_York'))
        # Send daily during Christmas:
        # scheduler.add_job(send_free_game_message, CronTrigger(hour=11, minute=3, jitter=180, timezone='US/Eastern'))


client = Bot(command_prefix=Utils.load_json('prefix'), case_insensitive=True, intents=intents)


async def send_free_game_message():
    channels = [751131240203026566, 688900848956342324]  # TODO get channel names from database
    for ch in channels:
        channel = client.get_channel(ch)
        await channel.send('https://www.epicgames.com/store/en-US/free-games')


@client.event
async def on_ready():
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
        return await ctx.send('Try again')

    print_log(str(error), ctx)


def print_log(error_name: str, ctx):
    collection = logs_db[str(ctx.guild.id)]
    log_message = f"{error_name} - {ctx.message.author} : {ctx.message.content}"
    utc_time = datetime.datetime.now(datetime.timezone.utc)

    db_log_post = {'date': utc_time, 'error': error_name, 'user_name': str(ctx.message.author), 'message_content': ctx.message.content,
                   'user_id': ctx.author.id, 'channel': ctx.message.channel.id, 'message_id': ctx.message.id}
    collection.insert_one(db_log_post)

    print(f'{utc_time} UTC: {log_message}')


client.run(os.environ.get('DISCORD_TOKEN'))