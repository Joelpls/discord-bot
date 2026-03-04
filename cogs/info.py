import discord
from discord.ext import commands


class Info(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print('Info cog ready')

    @commands.command(name='featurerequest', aliases=['request', 'fr'])
    async def feature_request(self, ctx, *, text):
        """Request a new feature for the discord bot!"""
        # TODO random insults
        await ctx.send(f'Add it yourself, bozo! But if you insist... '
                       f'https://github.com/Joelpls/discord-bot/issues/new?assignees=&labels=&template=feature_request.md&title='
                       f'{text.replace(" ", "%20")}')

    @commands.command()
    async def features(self, ctx):
        """Show a list of automatic bot features"""
        embed = discord.Embed(title='Automatic Features', color=discord.Color.blurple())
        embed.add_field(name='Counting', value='Enforces sequential counting in any channel named "counting". Deletes invalid messages and DMs the correct next number.', inline=False)
        embed.add_field(name='TikTok & Twitter/X', value='Automatically reposts TikTok and Twitter/X video links as a direct playable video.', inline=False)
        embed.add_field(name='YouTube Notifications', value='Posts new videos from subscribed YouTube channels to a designated channel or thread. Manage subscriptions with `!youtube`.', inline=False)
        await ctx.send(embed=embed)

    @commands.command(name='freegames', aliases=['freegame'])
    async def free_games(self, ctx):
        """Show this week's free games from the Epic Store"""
        await ctx.send('https://www.epicgames.com/store/en-US/free-games')


async def setup(client):
    await client.add_cog(Info(client))