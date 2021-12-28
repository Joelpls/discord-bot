import math
import random
import re
import time

import aiohttp
import discord
from discord.ext import commands
import pandas as pd

pd.set_option('display.max_rows', 1000)
import datetime
from fuzzywuzzy import process


class WaitTimes(commands.Cog):

    def __init__(self, client):
        self._CACHE_TIME = 60 * 3  # minutes
        self.client = client
        self.parks = ["WaltDisneyWorldMagicKingdom",
                      "WaltDisneyWorldEpcot",
                      "WaltDisneyWorldHollywoodStudios",
                      "WaltDisneyWorldAnimalKingdom",
                      "UniversalIslandsOfAdventure",
                      "UniversalStudiosFlorida"]
        self.df_parks_waittime = pd.DataFrame()
        self.spellings = []
        self.last_retrieve = 0

    @commands.Cog.listener()
    async def on_ready(self):
        print('Wait Times cog ready')

    async def get_parks_waittime(self):
        for park in self.parks:
            d = await get_park_async(park)
            df = pd.json_normalize(d)
            df = df[~(df["meta.type"] == 'RESTAURANT')]
            df['park'] = park
            columns = ["park", "name", "waitTime", "status", "active", "lastUpdate"]
            df = df.filter(columns)
            df['lastUpdate'] = pd.to_datetime(df['lastUpdate']).dt.tz_convert('America/New_York')
            self.df_parks_waittime = self.df_parks_waittime.append(df)

        self.make_spellings()
        self.last_retrieve = time.time()

        return self

    def make_spellings(self):
        self.spellings = self.df_parks_waittime['name'].astype(str).values.tolist()

    @commands.command(aliases=['wait', 'queue', 'queues', 'ride', 'rides', 'attraction', 'attractions'])
    async def waits(self, ctx, *, ride=None):
        """
        Get wait times for Orlando theme park attractions.
        """
        if ride is None:
            await ctx.send('Please choose an attraction.')
            return
        if ride.lower() == "update":
            await ctx.send('Wait times updated.')
            if self.last_retrieve != 0:
                await self.get_parks_waittime()
            return

        if time.time() - self.last_retrieve > self._CACHE_TIME:
            await self.get_parks_waittime()
            got_cache = True
        else:
            got_cache = False

        extract_spelling = process.extract(ride, self.spellings, limit=1)
        closest_word = extract_spelling[0][0]

        data = self.df_parks_waittime
        if got_cache:
            data.set_index("name", inplace=True)
            data.head()
        ride_embed = self.make_ride_embed(data.loc[closest_word])
        await ctx.send(embed=ride_embed)

    def make_ride_embed(self, ride_df):
        park = re.split('(?=[A-Z])', ride_df.park)
        name = ride_df.name
        wait_time = ride_df.waitTime
        status = ride_df.status
        active = ride_df.active
        last_update = ride_df.lastUpdate.to_pydatetime()
        if not pd.isnull(last_update):
            last_update = datetime.datetime(last_update.year, last_update.month, last_update.day,
                                            last_update.hour, last_update.minute, last_update.second)
        else:
            last_update = ''

        desc = ""
        if (status is None and not active) or wait_time is None or math.isnan(wait_time):
            desc = f'Status: Closed'
        elif status == "Closed" and math.isnan(wait_time):
            desc = f'Status: {status}'
        else:
            desc = f'**{int(wait_time)}** minutes\n' \
                   f'Status: {status}'

        desc += f'\n\n{" ".join(park).strip()}'

        embed = discord.Embed(
            title=name,
            description=desc,
            color=random.randint(1, 16777215)
        )
        embed.set_footer(text=f'{last_update}')

        return embed


async def get_park_async(park: str):
    async with aiohttp.ClientSession() as session:
        url_waittime = f"https://api.themeparks.wiki/preview/parks/{park}/waittime"
        async with session.get(url_waittime) as response:
            assert 200 == response.status, response.reason
            return await response.json()


def setup(client):
    client.add_cog(WaitTimes(client))
