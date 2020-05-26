# Meme Bot

A Discord bot with random fun commands.

## Getting Started

### Prerequisites

- Python 3
- see [requirements.txt](https://github.com/Joelpls/discord-bot/blob/master/requirements.txt)

### Installation

- setup environment variables:
  - DISCORD_TOKEN : your Bot Token from the discord developer portal
  - MONGODB_ADDRESS : your MongoDB address
  - IEX_PUB : your IEX Cloud key

TODO

## Usage

### Random Images

The images uploaded to the server will have their URLs stored in a MongoDB database. 
Using the discover or pick command will post an image randomly in the database. The images are specific to their channel.

```text
!discover 
(aliases = !d)
- Post one random image from the database.

!pick 
(aliases = !p)
- Display three random images and choose one to post.

!remove [URL (optional)] 
(aliases = !rm !delete !del !cursed)
- Removes the image URL from the database. Pass no URL to remove the image posted above this command.

!isremoved [URL (optional)]
(aliases = !isgone !indatabase !indb !isremove !isrm)
- Checks if the image is in the database. Pass no URL to check the image posted above this command.

!posted [URL]
- See who originally posted this image.

!stats
- See how many images are in this channel and total in the server.

!stats [@User]
- See how many images this user posted in this channel and server.

!undo
(aliases = !redo)
- Undoes the discover above this command.
```

### Other Commands

```text
!roll [ndm] (where n and m are digits)
(aliases = !r !dice)
- Roll n number of m-sided dice.
    Example to roll 2 6-sided dice: !roll 2d6

!8ball [question]
(aliases = !8-ball)
- Ask the Magic 8-Ball a question.

!reactions
- Shows the total number of reactions each user has received on their messages

!ban [User]
- Tell somebody to shutup.

!freegames
(aliases = !freegame)
- Get a link to this week's Epic Game Store free games.

!emote [emote]
(aliases = !em !me)
- Express yourself

!f [respectee (optional)]
(aliases = !respects !payrespect !respect !payrespects)
- Press f to pay respects.

!gt [message]
(aliases = !gt)
- Type your message in green text.

!logs [number (optional)]
(aliases = !errors !errorlogs)
- See incorrect commands passed to the bot. Get up to 25 messages. Default = 5.
```
### Ranks
Earn experience by sending messages. The more active you are, the higher rank you will achieve.

```text
!level [user (optional)]
- See a user's rank and xp level

!rank
(aliases = !ranks !rankings !ranking)
- View the rank of everyone on this server
```

### Food

!food (aliases = !eat !restaurant !restaurants)

```text
!food (or !food choose)
- Get a random restaurant recommendation from the database.

!food add [restaurant]
- Add a restaurant to the database.

!food remove [restaurant (optional)]
- Remove a restaurant from the database. Pass no restaurant to remove the one above this command.
```

### Stocks

Type `$<ticker>` to get stock quotes.  
I.e. `$MSFT`
