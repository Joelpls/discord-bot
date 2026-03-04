import os

from discord.ext import commands
from pymongo import MongoClient

cluster = MongoClient(os.environ.get('MONGODB_ADDRESS'), serverSelectionTimeoutMS=1000)
logs_db = cluster['Logs']


class Logs(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print('Logs cog ready')

    @commands.command(name='logs', aliases=['errors', 'errorlogs'])
    async def error_logs(self, ctx, num_logs=5):
        """Print out the latest error log messages. Defaults to 5. Limit 25."""
        collection = logs_db[str(ctx.guild.id)]
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


async def setup(client):
    await client.add_cog(Logs(client))