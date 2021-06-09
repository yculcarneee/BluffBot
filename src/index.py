import discord
from PIL import Image
import math
from discord.ext import commands 
from discord.utils import get

from dotenv import load_dotenv
import os
import random
import asyncio

load_dotenv()

token = os.getenv('DISCORD_TOKEN')

class BluffBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_id = 0
        self.player_list = []
        self.game_status = 'Initial'
        self.split = 0
        self.extra = 0
        self.channel_list = []
        self.hands = []
        self.hands_notation = []
        self.deck = [
            'deck/AD.png', 'deck/AC.png', 'deck/AH.png', 'deck/AS.png', 'deck/2D.png', 'deck/2C.png', 'deck/2H.png',
            'deck/2S.png', 'deck/3D.png', 'deck/3C.png', 'deck/3H.png', 'deck/3S.png',
            'deck/4D.png', 'deck/4C.png', 'deck/4H.png', 'deck/4S.png', 'deck/5D.png', 'deck/5C.png', 'deck/5H.png',
            'deck/5S.png', 'deck/6D.png', 'deck/6C.png', 'deck/6H.png', 'deck/6S.png',
            'deck/7D.png', 'deck/7C.png', 'deck/7H.png', 'deck/7S.png', 'deck/8D.png', 'deck/8C.png', 'deck/8H.png',
            'deck/8S.png', 'deck/9D.png', 'deck/9C.png', 'deck/9H.png', 'deck/9S.png',
            'deck/10D.png', 'deck/10C.png', 'deck/10H.png',
            'deck/10S.png', 'deck/JD.png', 'deck/JC.png', 'deck/JH.png', 'deck/JS.png', 'deck/QD.png', 'deck/QC.png',
            'deck/QH.png', 'deck/QS.png',
            'deck/KD.png', 'deck/KC.png', 'deck/KH.png', 'deck/KS.png'
        ]
        self.turn = 0

    async def update_embed(self, message, embed, index, new_embed_value):
        embed.set_field_at(index, name = embed.fields[index].name, value = new_embed_value, inline = False)
        await message.edit(embed = embed)

    async def fetch_message(self, channel_id, message_id):
        channel = bot.get_channel(channel_id)
        message = await channel.fetch_message(message_id)
        return message

    def convert_hand_to_image(self, hand, index):
        images = [Image.open(x) for x in hand]
        widths, heights = zip(*(i.size for i in images))

        width = max(widths)
        height = max(heights)

        total_width = 6 * width
        total_height = math.ceil(len(hand) / 6) * height

        new_im = Image.new('RGB', (total_width, total_height))

        x_offset, y_offset = 0, 0

        for idx, im in enumerate(images):
            im = im.resize((width, height))
            new_im.paste(im, (x_offset, y_offset))
            x_offset += im.size[0]
            if x_offset == total_width:
                x_offset = 0
                y_offset += im.size[1]

        new_im.save(f'hands/hand-{index}.jpg')

    def get_hands_notation(self):
        hands_notation = []

        for hand in self.hands:
            current_hand = []
            for card in hand:
                current_hand.append(card[5:7])
            hands_notation.append(current_hand)
        
        return hands_notation

    def divide_deck_into_hands(self):
        deck_copy = list(self.deck)
        random.shuffle(deck_copy)
        
        hands = []

        for hand_size in range(len(self.player_list)):
            hands.append(deck_copy[hand_size * self.split : (hand_size + 1) * self.split])
    
        random_players = random.sample(range(0, len(self.player_list)), self.extra)

        for random_player in random_players:
            hands[random_player].append(deck_copy.pop())
        
        for index, hand in enumerate(hands):
            self.convert_hand_to_image(hand, index + 1)

        return hands

    @commands.Cog.listener()
    async def on_ready(self):
        print('Logged in as')
        print(self.bot.user.name)
        print(self.bot.user.id)
        print('------')

    @commands.command()
    async def startgame(self, ctx):
        if self.game_status != 'Initial':
            embed = discord.Embed(title = 'Start Bluff Game', description = 'Can\'t start a new game before ending the previous one', color = 0xff0000)    
            await ctx.send(embed = embed)
            return 

        self.game_status = 'Lobby'
        embed = discord.Embed(title = 'Start Bluff Game', description = 'React to ✋ emoji to enter the game', color = 0xff0000)
        embed.add_field(name = 'Players', value = 'None', inline = False)
        embed.add_field(name = 'Time', value = '30 seconds to start the game!', inline = False)
        message = await ctx.send(embed = embed)
        
        self.message_id = message.id

        enter_game = '✋'
        await message.add_reaction(enter_game)

        await asyncio.sleep(10)
        updated_message = await self.fetch_message(message.channel.id, message.id)
        await self.update_embed(message, updated_message.embeds[0], 1, '20 seconds left to start the game!')

        await asyncio.sleep(10)
        updated_message = await self.fetch_message(message.channel.id, message.id)
        await self.update_embed(updated_message, updated_message.embeds[0], 1, '10 seconds left to start the game!')

        await asyncio.sleep(10)

        updated_message = await self.fetch_message(message.channel.id, message.id)
        updated_embed = updated_message.embeds[0]

        updated_player_list = updated_embed.fields[0].value.split(', ')

        if len(updated_player_list) > 1:
            self.player_list = updated_player_list

            default_overwrites = {
                ctx.guild.me: discord.PermissionOverwrite(view_channel = True),
                ctx.guild.default_role: discord.PermissionOverwrite(view_channel = False)
            }

            category_name = 'Bluff-Category'
            category = get(ctx.guild.categories, name = category_name)

            if category is None:
                category = await ctx.guild.create_category(category_name)

            for player in updated_player_list:
                overwrites = dict(default_overwrites)
                member = get(ctx.guild.members, name = player)
                overwrites[member] = discord.PermissionOverwrite(view_channel = True)

                if not get(ctx.guild.channels, name = f'{player}-bluff-channel'):
                    channel = await ctx.guild.create_text_channel(f'{player}-bluff-channel', overwrites = overwrites, category = category)
                    self.channel_list.append(channel)

            self.game_status = 'Playing'

            updated_embed.remove_field(1)
            updated_embed.add_field(name = 'Status', value = 'The game has begun!', inline = False)

            await updated_message.edit(embed = updated_embed)

            player_count = len(self.player_list)
    
            if len(self.deck) % player_count == 0:
                self.split = len(self.deck) // player_count
            else:
                self.split = len(self.deck) // player_count
                self.extra = len(self.deck) - player_count * self.split
            
            self.hands = self.divide_deck_into_hands()
            self.hands_notation = self.get_hands_notation()

            self.turn = random.choice(range(0, len(self.player_list)))

            for index, channel in enumerate(self.channel_list):
                file = discord.File(f'hands/hand-{index+1}.jpg')
                if index == self.turn:
                    hand_embed = discord.Embed(title = 'It\'s your turn!', color = 0xff0000)    
                else:
                    hand_embed = discord.Embed(title = f'It\'s {self.player_list[self.turn]}\'s turn!', color = 0xff0000)
                hand_embed.add_field(name = '\u200b', value = 'Your cards', inline = False)
                hand_embed.set_image(url = f'attachment://hand-{index+1}.jpg')
                hand_embed.set_footer(text = f'{self.player_list[(self.turn + 1) % len(self.player_list)]} goes next')
                await channel.send(file = file, embed = hand_embed)

        else:
            updated_embed.remove_field(0)
            updated_embed.remove_field(0)
            updated_embed.add_field(name = 'Status', value = 'Need at least 2 people to start the game :(', inline = False)
            
            self.game_status = 'Initial'

            await updated_message.edit(embed = updated_embed)

    @commands.command()
    async def cards(self, message):
        if self.game_status != 'Playing':
            embed = discord.Embed()
            embed.set_author(name = 'No game is currently in progress')
            await message.channel.send(embed = embed)
            return 

        index = self.player_list.index(message.author.name)

        if message.channel not in self.channel_list or message.channel != self.channel_list[index]:
            embed = discord.Embed()
            embed.set_author(name = 'You can only use this command in your Bluff channel')
            await message.channel.send(embed = embed)
            return
        
        current_hand = self.hands_notation[index]
        hand_embed = discord.Embed(title = 'Your cards', color = 0xff0000)    
        hand_embed.add_field(name = '\u200b', value = ', '.join(current_hand), inline = False)
        await message.channel.send(embed = hand_embed)
        

    @commands.command()
    async def endgame(self, ctx):
        if self.game_status == 'Initial':
            embed = discord.Embed(title = 'End Bluff Game', description = 'No Bluff games found to be ended', color = 0xff0000)    
            await ctx.send(embed = embed)
            return 

        for player in self.player_list:
            channel = get(ctx.guild.channels, name = f'{player}-bluff-channel')
            await channel.delete()
        
        self.game_status = 'Initial'
        self.split = 0
        self.extra = 0
        self.channel_list = []
        self.message_id = 0
        self.player_list = []

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.message_id != self.message_id or payload.member.name == self.bot.user.name or self.game_status != 'Lobby':
            return  

        message = await self.fetch_message(payload.channel_id, payload.message_id)
        embed = message.embeds[0]
        
        old_player_list = embed.fields[0].value.split(', ')
        if 'None' in old_player_list:
            old_player_list.remove('None')
        
        new_player_list = [*old_player_list, payload.member.name]

        await self.update_embed(message, embed, 0, ', '.join(new_player_list))
        
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.message_id != self.message_id or self.game_status != 'Lobby':
            return  

        message = await self.fetch_message(payload.channel_id, payload.message_id)
        embed = message.embeds[0]
        
        guild = await self.bot.fetch_guild(payload.guild_id)
        member = await guild.fetch_member(payload.user_id)
        
        old_player_list = embed.fields[0].value.split(', ')
        old_player_list.remove(member.name)
        
        if not old_player_list:
            old_player_list = ['None']

        await self.update_embed(message, embed, 0, ', '.join(old_player_list))


intents = discord.Intents.default()
intents.members = True

description = '''A bot which plays the card game Bluff'''

bot = commands.Bot(command_prefix = '/', description = description, intents = intents)

bot.add_cog(BluffBot(bot))

bot.run(token)
