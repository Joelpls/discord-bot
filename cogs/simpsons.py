from compuglobal.aio import Frinkiac
from compuglobal.aio import FrinkiHams
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType

from utils.tvshows import TVShowCog


class Simpsons(TVShowCog):
    def __init__(self, bot):
        super().__init__(bot, Frinkiac())
        self.frinkihams = FrinkiHams()

    # Messages a random Simpsons quote with gif if no search terms are given,
    # Otherwise, search for Simpsons quote using search terms and post gif
    @commands.command(aliases=['simpsonsgif', 'sgif'])
    @commands.cooldown(1, 3, BucketType.channel)
    @commands.guild_only()
    async def simpsons(self, ctx, *, search_terms: str = None):
        await self.post_gif(ctx, search_terms)


def setup(bot):
    bot.add_cog(Simpsons(bot))
