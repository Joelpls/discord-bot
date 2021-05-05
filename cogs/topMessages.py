import os

import discord
from discord.ext import commands
from pymongo import MongoClient
import datetime
import random
import time

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
        query = {"author_id": msg.author.id, "message_id": payload.message_id, "server": payload.guild_id,
                 "channel_id": payload.channel_id}
        insert_values = {"message_link": msg.jump_url, "date_created": utc_time, "bot": msg.author.bot}
        set_values = {"date_most_recent_reaction": utc_time}
        inc_values = {"reactions_all": sign * 1, "reactions_not_author": sign * other_react}

        collection.update_one(query,
                              {"$setOnInsert": insert_values, "$set": set_values, "$inc": inc_values},
                              upsert=True)

    @commands.command(aliases=['upboats', 'upvote', 'topmessages', 'topmsg', 'msg', 'messages', 'upboat'])
    async def upvotes(self, ctx, amount=10, include_self='True'):
        """Shows the messages with the most reactions"""
        reacts = 'reactions_all'
        if str(include_self).lower() == "false":
            reacts = 'reactions_not_author'

        collection = msg_db[str(ctx.guild.id)]

        # clean up old, low reacted to messages
        one_week_ago = datetime.datetime.utcnow() - datetime.timedelta(7)
        collection.delete_many({"date_created": {"$lte": one_week_ago}, "reactions_all": {"$lte": 5}})

        if amount > 20:
            amount = 20
        top_messages = collection.find({}).sort(reacts, -1).limit(amount)

        members = []
        async for mem in ctx.guild.fetch_members():
            members.append(mem)

        rank = ''
        index = 1
        for doc in top_messages:
            user = ctx.guild.get_member(doc['author_id'])
            if user is None:
                for mem in members:
                    if mem.id == doc['author_id']:
                        user = mem
            if user is None:
                continue

            channel = ctx.guild.get_channel(doc['channel_id'])
            msg = None
            try:
                msg = await channel.fetch_message(doc['message_id'])
            except discord.errors.NotFound:
                continue
            if msg is None:
                continue

            preview = ''
            if msg.clean_content:
                preview = f'- "{msg.clean_content[:40]}"'

            s = f'**{index})** {user.display_name} - Reactions: **{doc[reacts]}** {preview} {doc["message_link"]}\n'
            rank += s
            index += 1

        rank_embed = discord.Embed(title='Top Reacted to Messages', description=rank,
                                   color=discord.Color(random.randint(1, 16777215)))
        await ctx.send(embed=rank_embed)

    @commands.command(hidden=True)
    async def updatedb(self, ctx, amount=10, limit=20000):
        if ctx.author.id != 413139799453597698:
            await ctx.send("Not authorized to use command")
            return

        msg = await ctx.send('Updating database')

        collection = msg_db[str(ctx.guild.id)]
        collection.create_index([("reactions_all", -1)])
        collection.create_index([("reactions_not_author", -1)])
        collection.create_index([("reactions_all", -1), ("bot", 1)])
        collection.create_index([("reactions_not_author", -1), ("bot", 1)])
        collection.create_index([("date_created", -1)])
        collection.create_index([("date_created", 1)])

        queries = []
        start_time = time.monotonic()
        # TODO arguments to skip text channels
        for ch in ctx.guild.text_channels:
            await msg.edit(content=f'Updating #{ch.name}')
            messages = await ch.history(limit=limit).flatten()

            for mess in messages:
                total = 0
                # Skip if less than amount in command reactions
                for r in mess.reactions:
                    total += r.count
                if total < amount:
                    continue

                count = 0
                not_auth_count = 0  # number of reactions without self reacts

                for r in mess.reactions:
                    count += r.count
                    not_auth_count += r.count
                    async for user in r.users():
                        if mess.author == user:
                            not_auth_count -= 1

                query = {"author_id": mess.author.id, "message_id": mess.id, "server": mess.guild.id,
                         "channel_id": ch.id, "message_link": mess.jump_url, "date_created": mess.created_at,
                         "reactions_all": count, "reactions_not_author": not_auth_count,
                         "bot": mess.author.bot}
                queries.append(query)

        inserted = 0
        if len(queries) > 0:
            result = collection.insert_many(queries)
            inserted = len(result.inserted_ids)
        await msg.edit(content=f'Inserted {inserted} in {str(time.monotonic() - start_time)[:4]} seconds.')


def setup(client):
    client.add_cog(TopMessages(client))
