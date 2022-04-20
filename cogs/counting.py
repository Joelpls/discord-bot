from discord.ext import commands


class Counting(commands.Cog):

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        print('Counting cog ready')

    @commands.Cog.listener()
    async def on_message(self, message):
        # Don't do this in DMs
        if not message.guild:
            return

        # TODO add channel ID to database instead of checking if called "counting"
        # TODO set a channel as binary or decimal
        # check if channel is named "counting"
        channel = message.channel
        if "counting" not in channel.name:
            return

        # Delete message if bot or not numeric or negative or has leading zeroes
        content = message.content
        if message.author.bot \
                or not content.isnumeric() \
                or "-" in content \
                or (content.startswith('0') and len(content) > 1)\
                or len(message.attachments) > 0:
            await message.delete()
            return

        try:
            messages = await channel.history(limit=3).flatten()
            # Get previous number
            previous_number_str = messages[1].content
            previous_num = int(previous_number_str)

            # Try to get them if they're binary. Some bugs could occur if the next number is the same in binary and decimal.
            current_num_binary = 0
            previous_num_binary = 0
            try:
                previous_num_binary = int(previous_number_str, 2)
                current_num_binary = int(content, 2)
            except ValueError:
                pass

            # Check if it's 1 more
            current_num = int(content)
            if current_num != previous_num + 1 \
                    and current_num_binary != previous_num_binary + 1:
                await message.delete()

                # Send DM of correct number.
                try:
                    two_nums_ago_binary = int(messages[2].content, 2)
                    if previous_num_binary - two_nums_ago_binary == 1:
                        await message.author.send(f"The next number is {bin(previous_num_binary + 1)[2:]}", delete_after=300)
                        return
                except ValueError:
                    pass

                two_nums_ago = int(messages[2].content)
                if previous_num - two_nums_ago == 1:
                    await message.author.send(f"The next number is {previous_num + 1}", delete_after=300)
                    return

        except IndexError:
            # We only start at 0 or 1
            if content != '0' and content != '1':
                await message.delete()
            return


def setup(client):
    client.add_cog(Counting(client))
