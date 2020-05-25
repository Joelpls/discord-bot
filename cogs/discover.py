import os
import discord
import json
from discord.ext import commands
from pymongo import MongoClient
import re
from PIL import Image
import copy
import shutil
import requests
import uuid


def load_json(token):
    with open('./config.json') as f:
        config = json.load(f)
    return config.get(token)


cluster = MongoClient(load_json('db_address'))
db = cluster['Discord']
discover_images = cluster['Discover_Images']


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
        if message.author.id != load_json('bot_id') and not message.author.bot:
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
    @commands.command(aliases=['p'])
    async def pick(self, ctx, num=3):
        """Discover three random images and pick one to send."""

        # If 1 was passed in, just call the discover command.
        if num == 1:
            await self.discover(ctx)
            return
        elif num != 3:
            await ctx.send('Usage: "!p" or "!pick"\n'
                           '"!p" to choose from 3 random images.\n'
                           '"!p 1" to get a single random image, or use the !discover command."')
            return

        # Get 3 random images
        collection = db[str(ctx.guild.id)]
        query = [{"$match": {"channel": ctx.channel.id}}, {"$sample": {"size": 3}}]
        images = collection.aggregate(query)

        files = []

        # Store the images locally and get their discord image URLs
        image_urls = await store_images_locally(files, images)

        if len(image_urls) < 3:
            await ctx.send(f"Upload more images. There's {len(image_urls)} in this channel.")
            return

        # Combine the images into one. Store locally with a random name (Gets deleted later).
        image_list = map(Image.open, files)
        new_image = append_images(image_list)
        combo_image_name = f'./cogs/images/{str(uuid.uuid4())[:8]}.jpg'
        new_image.save(f'{combo_image_name}')

        # Send the combined image.
        sent = await ctx.send(f"{ctx.message.author.display_name}'s discover:", file=discord.File(combo_image_name),
                              delete_after=300)
        await ctx.message.delete()

        # Store the message ID of the new combined image message.
        collection_disc = discover_images[str(ctx.guild.id)]
        disc_query = {"message_id": sent.id, "message_author": ctx.author.id, "channel_id": ctx.channel.id}
        collection_disc.insert_one(disc_query)

        # Add reactions to the new message so the user can choose one to send.
        await sent.add_reaction('1️⃣')
        await sent.add_reaction('2️⃣')
        await sent.add_reaction('3️⃣')
        await sent.add_reaction('\U0001F1FD')

        # Store the individual image URLs of the combo images in DB
        index = 1
        for image in image_urls:
            collection_disc.update_one(disc_query, {'$set': {f'image{index}': image}})
            index += 1

        # Remove the stored images
        for file in files:
            if os.path.isfile(file):
                os.remove(file)
        if os.path.isfile(combo_image_name):
            os.remove(combo_image_name)

    # Randomly posts an image that has been posted before
    @commands.command(aliases=['d'])
    async def discover(self, ctx):
        """Randomly posts an image previously uploaded to this channel."""
        await ctx.message.delete()
        collection = db[str(ctx.guild.id)]
        query = [{"$match": {"channel": ctx.channel.id}}, {"$sample": {"size": 1}}]
        images = collection.aggregate(query)
        if images.alive:
            for image in images:
                await ctx.send(f"{ctx.message.author.display_name} discovered {image['url']}")
        else:
            await ctx.send('No images to discover \U0001F622\nUpload some!')

    # check the emoji chosen
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if not user.bot:
            collection_disc = discover_images[str(user.guild.id)]
            document = collection_disc.find_one(
                {"message_id": reaction.message.id, "channel_id": reaction.message.channel.id})
            og_user = document.get('message_author')

            # If the user who called the discover == the user who reacted
            if og_user == user.id:
                if str(reaction) == '1️⃣':
                    image = document.get('image1')
                    await reaction.message.channel.send(f"{user.display_name} discovered {image}")
                    collection_disc.delete_one({"message_id": reaction.message.id})
                    await reaction.message.delete()
                elif str(reaction) == '2️⃣':
                    image = document.get('image2')
                    await reaction.message.channel.send(f"{user.display_name} discovered {image}")
                    collection_disc.delete_one({"message_id": reaction.message.id})
                    await reaction.message.delete()
                elif str(reaction) == '3️⃣':
                    image = document.get('image3')
                    await reaction.message.channel.send(f"{user.display_name} discovered {image}")
                    collection_disc.delete_one({"message_id": reaction.message.id})
                    await reaction.message.delete()
                elif str(reaction) == '🇽':
                    collection_disc.delete_one({"message_id": reaction.message.id})
                    await reaction.message.delete()
                    return

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

    @commands.command()
    async def stats(self, ctx):
        """See how many images are in the database. @user for their stats."""
        try:
            name = ctx.message.mentions[0]
            await poster(ctx, name)
        except IndexError:
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


def append_images(images, direction='horizontal', bg_color=(255, 255, 255), alignment='center'):
    """
    Appends images in horizontal/vertical direction.

    Args:
        images: List of PIL images
        direction: direction of concatenation, 'horizontal' or 'vertical'
        bg_color: Background color (default: white)
        alignment: alignment mode if images need padding;
           'left', 'right', 'top', 'bottom', or 'center'

    Returns:
        Concatenated image as a new PIL image object.
    """
    images1 = copy.deepcopy(images)
    widths, heights = zip(*(i.size for i in images))

    if direction == 'horizontal':
        new_width = sum(widths)
        new_height = max(heights)
    else:
        new_width = max(widths)
        new_height = sum(heights)

    new_im = Image.new('RGB', (new_width, new_height), color=bg_color)

    offset = 0
    for im in images1:
        if direction == 'horizontal':
            y = 0
            if alignment == 'center':
                y = int((new_height - im.size[1]) / 2)
            elif alignment == 'bottom':
                y = new_height - im.size[1]
            new_im.paste(im, (offset, y))
            offset += im.size[0]
        else:
            x = 0
            if alignment == 'center':
                x = int((new_width - im.size[0]) / 2)
            elif alignment == 'right':
                x = new_width - im.size[0]
            new_im.paste(im, (x, offset))
            offset += im.size[1]

    return new_im


# Get stats of single user
async def poster(ctx, name):
    """Stats of a single user"""

    collection = db[str(ctx.guild.id)]
    query = {"channel": ctx.channel.id, "op": name.id}
    channel_count = collection.count_documents(query)
    server_count = collection.count_documents({"op": name.id})

    await ctx.send(f'{name.display_name} posted {channel_count} images in this channel.\n'
                   f'{name.display_name} posted {server_count} images in this server.')


async def store_images_locally(files, images):
    image_urls = []
    if images.alive:
        # Get the URL of each image. Store in image_urls
        # Download and store the image locally. (Will be combined and deleted later)
        # Store the local images in the "files" list. (So we know what to delete)
        for image in images:
            image_url = image['url']
            image_urls.append(image_url)
            filename, file_extension = os.path.splitext(image_url)

            directory = './cogs/images/'
            local_file = f'{directory}{str(uuid.uuid4())[:8]}{file_extension}'

            # Download the file locally
            r = requests.get(image_url, stream=True)
            if r.status_code == 200:
                if not os.path.exists(directory):
                    os.makedirs(directory)
                with open(local_file, 'wb') as f:
                    r.raw.decode_content = True
                    shutil.copyfileobj(r.raw, f)

                files.append(local_file)
    return image_urls


def setup(client):
    client.add_cog(Discover(client))
