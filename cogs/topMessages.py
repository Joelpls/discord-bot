import os
import discord
from discord.ext import commands
from pymongo import MongoClient
import datetime
import random

cluster = MongoClient(os.environ.get('MONGODB_ADDRESS'))
msg_db = cluster['TopMessages']


class TopMessages(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print('Top messages cog ready')

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        await self.update_msg_reaction_db(payload, 1)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        await self.update_msg_reaction_db(payload, -1)

    async def update_msg_reaction_db(self, payload, sign):
        collection = msg_db[str(payload.guild_id)]

        channel = self.client.get_channel(payload.channel_id)
        msg = await channel.fetch_message(payload.message_id)

        # If message author is same as reactor
        other_react = 0 if msg.author.id == payload.user_id else 1

        utc_time = datetime.datetime.utcnow()
        query = {"author_id": msg.author.id, "message_id": payload.message_id, "server": payload.guild_id}
        insert_values = {"message_link": msg.jump_url, "date_created": utc_time}
        set_values = {"date_most_recent_reaction": utc_time}
        inc_values = {"reactions_all": sign * 1, "reactions_not_author": sign * other_react}

        collection.update_one(query,
                              {"$setOnInsert": insert_values, "$set": set_values, "$inc": inc_values},
                              upsert=True)

    @commands.command(aliases=['upboats', 'upvote', 'topmessages', 'topmsg', 'msg', 'messages'])
    async def upvotes(self, ctx, include_self='True'):
        reacts = 'reactions_all'
        if str(include_self).lower() == "false":
            reacts = 'reactions_not_author'

        collection = msg_db[str(ctx.guild.id)]

        # clean up old, low reacted to messages
        two_weeks_ago = datetime.datetime.utcnow() - datetime.timedelta(14)
        collection.delete_many({"date_created": {"$lte": two_weeks_ago}, "reactions_all": {"$lte": 3}})

        top_messages = collection.find({}).sort(reacts, -1).limit(10)

        rank = ''
        index = 1
        for doc in top_messages:
            user = self.client.get_user(doc['author_id'])
            msg = await ctx.fetch_message(doc['message_id'])
            preview = ''
            if msg.clean_content:
                preview = f'- "{msg.clean_content}"'

            s = f'**{index})** {user.display_name} - Reactions: **{doc[reacts]}** {preview} {doc["message_link"]}\n'
            rank += s
            index += 1

        rank_embed = discord.Embed(title='Top Reacted to Messages', description=rank,
                                   color=discord.Color(random.randint(1, 16777215)))
        await ctx.send(embed=rank_embed)


def setup(client):
    client.add_cog(TopMessages(client))
