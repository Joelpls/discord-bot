import discord
from discord.ext import commands
import json
from pymongo import MongoClient


def load_json(token):
    with open('./config.json') as f:
        config = json.load(f)
    return config.get(token)


cluster = MongoClient(load_json('db_address'))
db = cluster['Food']


class Food(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print('Food cog ready')

    @commands.command(aliases=['eat', 'restaurant', 'restaurants'])
    async def food(self, ctx, *, message=None):
        """add, choose, or remove restaurants to get random recommendations."""
        if message is None:
            await choose_restaurant(ctx)
            return

        # Split the command and restaurant.
        try:
            command, restaurant = message.split(' ', 1)
        # No restaurant was passed in.
        except ValueError:
            command = message
            restaurant = None

        command_lower = command.lower()
        if command_lower == 'add' or command_lower == 'include':
            if restaurant is not None:
                await add_restaurant_to_db(ctx, restaurant)
            else:
                await ctx.send('To add a restaurant run: ```!food add <restaurant>```')

        elif command_lower == 'choose' or command_lower == 'pick':
            await choose_restaurant(ctx)

        elif command_lower == 'remove' or command_lower == 'rm':
            if restaurant is not None:
                await remove_restaurant(ctx, restaurant)
            else:
                await remove_restaurant(ctx)

        else:
            await ctx.send('To add a restaurant run: ```!food add <restaurant>```\n'
                           'To get a restaurant recommendation run: ```!food or !food choose```\n'
                           'To remove a restaurant run ```!food remove <restaurant>``` '
                           'or omit the restaurant to remove the one in the message above.')


async def add_restaurant_to_db(ctx, restaurant):
    collection = db[str(ctx.guild.id)]
    post = {"op": ctx.message.author.id, "restaurant": restaurant, "channel": ctx.channel.id, "likes": 0, "dislikes": 0}
    collection.insert_one(post)


async def choose_restaurant(ctx):
    collection = db[str(ctx.guild.id)]
    query = [{"$sample": {"size": 1}}]
    chosen = collection.aggregate(query)

    if chosen.alive:
        for place in chosen:
            await ctx.send(place.get('restaurant'))
    else:
        await ctx.send('No restaurants to choose from.')


async def remove_restaurant(ctx, restaurant=None):
    collection = db[str(ctx.guild.id)]

    if restaurant:
        query = {"restaurant": restaurant}
    # Else remove the last message
    else:
        try:
            messages = await ctx.history(limit=2).flatten()
            restaurant = messages[1].content
            query = {"restaurant": restaurant}
        except IndexError:
            await ctx.send("Failed to remove restaurant")
            return

    result = collection.delete_one(query)
    if result.deleted_count == 1:
        await ctx.send(f"Removed {restaurant}")
    elif result.deleted_count == 0:
        await ctx.send(f"Failed to remove {restaurant}")
    else:
        await ctx.send("Something bad happened")


# TODO add likes and dislikes to messages
# TODO check if restaurant already in database (remove punctuation)
# TODO view all restaurants
# TODO get multiple recommendations in a single message

def setup(client):
    client.add_cog(Food(client))
