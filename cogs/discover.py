import discord
import json
from discord.ext import commands
from pymongo import MongoClient
import re


def load_json(token):
    with open('./config.json') as f:
        config = json.load(f)
    return config.get(token)


cluster = MongoClient(load_json('db_address'))
db = cluster['Discord']


async def create_indices(collection):
    collection.create_index([("channel", 1)])
    collection.create_index([("channel", 1), ("message_id", -1)])
    collection.create_index([("url", 1)])
    collection.create_index([("channel", 1), ("url", -1)])
    collection.create_index([("channel", 1), ("op", 1)])


class Discover(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print('Discover cog ready')

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id != load_json('bot_id'):
            try:
                image = message.attachments[0].url
                suffix_list = ['jpg', 'jpeg', 'png', 'gif']
                if image.casefold().endswith(tuple(suffix_list)):
                    collection = db[str(message.guild.id)]
                    post = {"channel": message.channel.id, "url": image, "op": message.author.id,
                            "message_id": message.id}
                    await create_indices(collection)
                    collection.insert_one(post)
                else:
                    pass
            except IndexError:
                pass

    # Remove the message from the database if a user deletes the message from the server
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        collection = db[str(message.guild.id)]
        query = {"channel": message.channel.id, "message_id": message.id}
        collection.delete_one(query)

    # Randomly posts an image that has been posted before
    @commands.command(aliases=['pick', 'd', 'p'])
    async def discover(self, ctx, num=1):
        """Discover up to 3 images"""
        await ctx.message.delete()
        if num < 1:
            num = 1
        elif num > 3:
            num = 3
        collection = db[str(ctx.guild.id)]
        query = [{"$match": {"channel": ctx.channel.id}}, {"$sample": {"size": num}}]
        images = collection.aggregate(query)
        if images.alive:
            for image in images:
                await ctx.send(f"{ctx.message.author.display_name} discovered {image['url']}")
        else:
            await ctx.send('No images to discover \U0001F622\nUpload some!')

    @commands.command(aliases=['delete', 'del', 'rm', 'cursed'])
    async def remove(self, ctx, url=None):
        """remove the URL of an image: !rm <url>"""
        collection = db[str(ctx.guild.id)]

        if url:
            query = {"channel": ctx.channel.id, "url": url}
        # Else remove the last message
        else:
            try:
                messages = await ctx.history(limit=2).flatten()
                msg_id = messages[1].id
                query = {"channel": ctx.channel.id, "message_id": msg_id}
            except IndexError:
                await ctx.send("Failed to remove image")
                return

        result = collection.delete_one(query)
        if result.deleted_count == 1:
            await ctx.send("Image removed")
        elif result.deleted_count == 0:
            await ctx.send("Failed to remove image")
        else:
            await ctx.send("Something bad happened")

    @commands.command(aliases=['isgone', 'indatabase', 'indb', 'isremove', 'isrm'])
    async def isremoved(self, ctx, url=None):
        """Check if the image is removed from the database"""
        collection = db[str(ctx.guild.id)]

        if url:
            query = {"channel": ctx.channel.id, "url": url}
        # Check the last message
        else:
            try:
                messages = await ctx.history(limit=2).flatten()
                msg_id = messages[1].id
                query = {"channel": ctx.channel.id, "message_id": msg_id}
            except IndexError:
                await ctx.send("I'm not sure")
                return

        if collection.count_documents(query, limit=1) == 0:
            await ctx.send("Image is not in the database")
        elif collection.count_documents(query, limit=1) != 0:
            await ctx.send("Image is still in the database")
        else:
            await ctx.send("I'm not sure")

    @commands.command()
    async def posted(self, ctx, url):
        """See who originally posted an image: !posted <url>"""
        collection = db[str(ctx.guild.id)]
        query = {"channel": ctx.channel.id, "url": url}
        op = collection.find_one(query)
        try:
            user = self.client.get_user(op['op'])
            await ctx.send(f'That was originally posted by: {user.display_name}')
        except TypeError:
            await ctx.send('I\'m not sure who posted that.')

    # Get stats of single user
    @commands.command()
    async def poster(self, ctx):
        """Stats of a single user"""
        name = ctx.message.mentions[0]

        collection = db[str(ctx.guild.id)]
        query = {"channel": ctx.channel.id, "op": name.id}
        channel_count = collection.count_documents(query)
        server_count = collection.count_documents({"op": name.id})

        await ctx.send(f'{name.display_name} posted {channel_count} images in this channel.\n'
                       f'{name.display_name} posted {server_count} images in this server.')

    @commands.command()
    async def stats(self, ctx):
        """See how many images are in the database"""
        # Guild data
        collection_str = str(db[str(ctx.guild.id)].name)
        dbstats = db.command('collstats', collection_str, {"match": {"channel": ctx.channel.id}})
        data_size = dbstats['size'] / 1024
        count = dbstats['count']

        # Channel data
        collection = db[str(ctx.guild.id)]
        query = {"channel": ctx.channel.id}
        channel_count = collection.count_documents(query)

        await ctx.send(f'Channel Images: {channel_count}\nServer Images: {count}\n'
                       f'Server Data Size: {round(data_size, 2)} KB')

    @commands.command(aliases=['redo'])
    async def undo(self, ctx, msg_id=None):
        """undo the discover immediately above this command"""
        collection = db[str(ctx.guild.id)]

        if msg_id:
            try:
                bot_msg = await ctx.fetch_message(msg_id)
            except (discord.NotFound, discord.HTTPException, discord.Forbidden) as e:
                await ctx.send('Message not found')
                return
        else:
            messages = await ctx.history(limit=2).flatten()
            bot_msg = messages[1]  # message above !undo command
            pattern = re.compile(r'(?=https://)([^\s]+)')  # regex to get URL in the message
            try:
                url = re.findall(pattern, bot_msg.content)[0]  # Get the first URL of the message
            except IndexError:
                url = ''

        query = {"channel": ctx.channel.id, "url": url}

        if bot_msg.author.bot and (collection.count_documents(query, limit=1) != 0):
            await bot_msg.edit(content='Discover undone by ' + ctx.message.author.display_name)
            await ctx.message.delete()
        else:
            await ctx.send('Not deleted')


def setup(client):
    client.add_cog(Discover(client))
