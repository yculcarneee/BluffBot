# TODO: Refactor entire bot to use objects and id's instead of names
import discord
from PIL import Image
from discord.ext import commands 
from discord.utils import get
from dotenv import load_dotenv

import os
import re
import random
import asyncio
from operator import itemgetter
import itertools
import math


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
        self.values_sort_order = {'A': 0, '2': 1, '3': 2, '4': 3, '5': 4, '6': 5, '7': 6, '8': 7, '9': 8, '10': 9, 'J': 10, 'Q': 11, 'K': 12}
        self.suits_sort_order = {'C': 0, 'D': 1, 'H': 2, 'S': 3}
        self.current_pot = []
        self.cards_flag = 'Initial'
        self.bluff_flag = 'Initial'
        self.current_bluff = {}
        self.round_initiated = False
        self.passed_list = []

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
                card_notation = card.split('/')[1][:-4]
                current_hand.append(card_notation)
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

    def order_hand_by_values(self, hand):
        return sorted(hand, key=lambda card: (self.values_sort_order[card[:-1]], card[-1]))

    def order_hand_by_suits(self, hand):
        return sorted(hand, key=lambda card: (self.suits_sort_order[card[-1]], self.values_sort_order[card[:-1]]))

    def get_hand_as_numbered_list(self, hand):
        numbered_list = ''
        for index, card in enumerate(hand):
            numbered_list += f'{index + 1}. {card}\n'
        return numbered_list

    def remove_cards_from_hand(self, cards_indices, index):
        for i in sorted(cards_indices, reverse = True):
            del self.hands[index][i]
            del self.hands_notation[index][i]

    def check_cards_played(self, cards, current_hand, index):
        cards_from_hand_range = re.search(r"^[0-9]+ *- *[0-9]+\Z", cards)
        cards_from_hand_individual = re.search(r"^([0-9 ,]+)\Z", cards)

        if cards_from_hand_range is None and cards_from_hand_individual is None:
            return False

        cards_from_hand = None
        if cards_from_hand_range is None:
            cards_from_hand = cards_from_hand_individual
        else:
            cards_from_hand = cards_from_hand_range

        cards = None
        if '-' in cards_from_hand.group():
            left_bound, right_bound = cards_from_hand.group().split('-')
            left_bound, right_bound = int(left_bound), int(right_bound)

            if left_bound < 1 or right_bound > len(current_hand) or left_bound >= right_bound:
                return False

            cards = current_hand[int(left_bound) - 1 : int(right_bound)]

            self.remove_cards_from_hand([*range(int(left_bound) - 1, int(right_bound))], index)
        else:
            cards_indices = cards_from_hand.group().split(',')
            cards_indices[:] = [int(card) - 1 for card in cards_indices]    

            if any(card_index > len(current_hand) - 1 or card_index < 0 for card_index in cards_indices):
                return False

            cards = itemgetter(*cards_indices)(current_hand)

            if isinstance(cards, str):
                cards = [cards]
            else:
                cards = list(cards)

            if len(set(cards)) != len(cards):
                return False

            self.remove_cards_from_hand(cards_indices, index)

        self.current_pot.append(cards)

        return True

    def check_bluff_played(self, bluff, current_hand):
        bluff_match = re.search(r"^[0-9]+ *- *([2-9]|10|[J,K,A,Q])\Z", bluff)

        if bluff_match is None:
            return False

        bluff = bluff_match.group()

        number_of_cards_str, type_of_cards_str = bluff.split('-')
        number_of_cards = int(number_of_cards_str)
        
        if number_of_cards < 1 or number_of_cards > len(current_hand) or len(self.current_pot[-1]) != number_of_cards:
            return False

        self.current_bluff = {
            'number_of_cards': number_of_cards,
            'type_of_cards': type_of_cards_str
        }
        
        return True

    def call_bluff(self, previous_hand):
        for card in previous_hand:
            if card[:-1] != self.current_bluff['type_of_cards']:
                return True

        return False

    def clear_round_state(self):
        self.current_pot = []
        self.current_bluff = {}
        self.round_initiated = False
        self.passed_list = []

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

            self.turn = random.randint(0, len(self.player_list) - 1)

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
            embed.set_author(name = 'You can only use this command in your own Bluff channel')
            await message.channel.send(embed = embed)
            return
        
        current_hand = self.hands_notation[index]
        hand_embed = discord.Embed(title = 'Your cards', color = 0xff0000)    
        hand_embed.add_field(name = '\u200b', value = self.get_hand_as_numbered_list(current_hand), inline = False)
        await message.channel.send(embed = hand_embed)
        
    @commands.command()
    async def shuffle(self, message, arg = None):
        if self.game_status != 'Playing':
            embed = discord.Embed()
            embed.set_author(name = 'No game is currently in progress')
            await message.channel.send(embed = embed)
            return 

        index = self.player_list.index(message.author.name)

        if message.channel not in self.channel_list or message.channel != self.channel_list[index]:
            embed = discord.Embed()
            embed.set_author(name = 'You can only use this command in your own Bluff channel')
            await message.channel.send(embed = embed)
            return

        if arg == 'suits':
            self.hands_notation[index] = self.order_hand_by_suits(self.hands_notation[index])
            hand_embed = discord.Embed(title = 'Your cards', color = 0xff0000)    
            hand_embed.add_field(name = '\u200b', value = self.get_hand_as_numbered_list(self.hands_notation[index]), inline = False)
            await message.channel.send(embed = hand_embed)
        elif arg == 'values':
            self.hands_notation[index] = self.order_hand_by_values(self.hands_notation[index])
            hand_embed = discord.Embed(title = 'Your cards', color = 0xff0000)    
            hand_embed.add_field(name = '\u200b', value = self.get_hand_as_numbered_list(self.hands_notation[index]), inline = False)
            await message.channel.send(embed = hand_embed)
        elif arg is None:
            embed = discord.Embed()
            embed.set_author(name = 'You need to pass a shuffling method after /shuffle. The available options are \'suits\' and \'values\'')
            await message.channel.send(embed = embed)
            return
        else:
            embed = discord.Embed()
            embed.set_author(name = 'Invalid option sent with /shuffle. The available options are \'suits\' and \'values\'')
            await message.channel.send(embed = embed)
            return

    @commands.command()
    async def play(self, message):
        if self.game_status != 'Playing':
            embed = discord.Embed()
            embed.set_author(name = 'No game is currently in progress')
            await message.channel.send(embed = embed)
            return 

        index = self.player_list.index(message.author.name)

        if message.channel not in self.channel_list or message.channel != self.channel_list[index]:
            embed = discord.Embed()
            embed.set_author(name = 'You can only use this command in your own Bluff channel')
            await message.channel.send(embed = embed)
            return

        if self.turn != index:
            embed = discord.Embed()
            embed.set_author(name = f'Wait till your turn to play')
            await message.channel.send(embed = embed)
            return      

        if self.round_initiated:
            embed = discord.Embed()
            embed.set_author(name = f'A round is currently in progress. You can only add cards to the pot using /add, pass this round using /pass, or challenge the last player\'s bluff using /challenge when it\'s your turn.')
            await message.channel.send(embed = embed)
            return      

        if self.cards_flag != 'Initial' or self.bluff_flag != 'Initial':
            return

        channel = message.channel
        current_hand = self.hands_notation[index]

        self.cards_flag = 'Processing'

        while self.cards_flag == 'Processing':
            await channel.send('What cards do you want to play?')

            def message_check(message):
                return message.channel == channel and message.author.name in self.player_list

            cards = await bot.wait_for('message', check = message_check)

            if self.player_list.index(cards.author.name) != index:
                embed = discord.Embed()
                embed.set_author(name = f'Wait till your turn to play')
                await message.channel.send(embed = embed)
                continue

            if cards.channel != channel:
                embed = discord.Embed()
                embed.set_author(name = 'You can only play in your own Bluff channel')
                await message.channel.send(embed = embed)
                return

            if not self.check_cards_played(cards.content, current_hand, index):
                embed = discord.Embed()
                embed.add_field(name = '\u200b', value = f'Cards to be played should be in the format **`range of indices of cards from your hand/specific indices of cards from your hand seperated by a comma`**')
                await channel.send(embed = embed)
            else:
                self.cards_flag = 'Initial'

        # await channel.send(self.current_pot)

        self.bluff_flag = 'Processing'

        while self.bluff_flag == 'Processing':
            await channel.send('What bluff do you want to make?')

            def message_check(message):
                return message.channel == channel and message.author.name in self.player_list

            bluff = await bot.wait_for('message', check = message_check)
            
            if not self.check_bluff_played(bluff.content, current_hand):
                embed = discord.Embed()
                embed.add_field(name = '\u200b', value = f'Invalid bluff')
                await channel.send(embed = embed)
            else:
                self.bluff_flag = 'Initial'
        
        # await channel.send(self.current_bluff)

        for index, channel in enumerate(self.channel_list):
            embed = None
            if index == self.turn:
                embed = discord.Embed(title = f'You played {self.current_bluff.get("number_of_cards")} {self.current_bluff.get("type_of_cards")}')
            else:
                embed = discord.Embed(title = f'{self.player_list[self.turn]} played {self.current_bluff.get("number_of_cards")} {self.current_bluff.get("type_of_cards")}')
            embed.set_footer(text = f'{self.player_list[(self.turn + 1) % len(self.player_list)]} goes next')
            await channel.send(embed = embed)

        self.turn = (self.turn + 1) % len(self.player_list)
        
        self.round_initiated = True

    @commands.command()
    async def add(self, message):
        if self.game_status != 'Playing':
            embed = discord.Embed()
            embed.set_author(name = 'No game is currently in progress')
            await message.channel.send(embed = embed)
            return 

        index = self.player_list.index(message.author.name)

        if message.channel not in self.channel_list or message.channel != self.channel_list[index]:
            embed = discord.Embed()
            embed.set_author(name = 'You can only use this command in your own Bluff channel')
            await message.channel.send(embed = embed)
            return

        if self.turn != index:
            embed = discord.Embed()
            embed.set_author(name = f'Wait till your turn to play')
            await message.channel.send(embed = embed)
            return      

        if not self.round_initiated:
            embed = discord.Embed()
            embed.set_author(name = 'No round is currently in progress right now')
            await message.channel.send(embed = embed)
            return 

        if self.cards_flag != 'Initial':
            return

        channel = message.channel
        current_hand = self.hands_notation[index]

        self.cards_flag = 'Processing'

        while self.cards_flag == 'Processing':
            await channel.send('What cards do you want to play?')

            def message_check(message):
                return message.channel == channel and self.player_list.index(message.author.name) == index

            cards = await bot.wait_for('message', check = message_check)

            if self.player_list.index(cards.author.name) != index:
                embed = discord.Embed()
                embed.set_author(name = f'Wait till your turn to play')
                await message.channel.send(embed = embed)
                continue

            if cards.channel != channel:
                embed = discord.Embed()
                embed.set_author(name = 'You can only play in your own Bluff channel')
                await message.channel.send(embed = embed)
                return

            if not self.check_cards_played(cards.content, current_hand, index):
                embed = discord.Embed()
                embed.add_field(name = '\u200b', value = f'Cards to be played should be in the format **`range of indices of cards from your hand/specific indices of cards from your hand seperated by a comma`**')
                await channel.send(embed = embed)
            else:
                self.cards_flag = 'Initial'

        await channel.send(self.current_pot)

        turn = self.turn

        self.turn = (self.turn + 1) % len(self.player_list)

        while self.turn in self.passed_list:
            self.turn = (self.turn + 1) % len(self.player_list)

        for index, channel in enumerate(self.channel_list):
            embed = None
            if index == turn:
                embed = discord.Embed(title = f'You added {len(self.current_pot[-1])} card(s) to the pot')
            else:
                embed = discord.Embed(title = f'{self.player_list[turn]} added {len(self.current_pot[-1])} card(s) to the pot')
            embed.set_footer(text = f'{self.player_list[self.turn]} goes next')
            await channel.send(embed = embed)

        # self.turn = (self.turn + 1) % len(self.player_list)

    @commands.command()
    async def passround(self, message):
        if self.game_status != 'Playing':
            embed = discord.Embed()
            embed.set_author(name = 'No game is currently in progress')
            await message.channel.send(embed = embed)
            return 

        index = self.player_list.index(message.author.name)

        if message.channel not in self.channel_list or message.channel != self.channel_list[index]:
            embed = discord.Embed()
            embed.set_author(name = 'You can only use this command in your own Bluff channel')
            await message.channel.send(embed = embed)
            return

        if self.turn != index:
            embed = discord.Embed()
            embed.set_author(name = f'Wait till your turn to play')
            await message.channel.send(embed = embed)
            return      

        if not self.round_initiated:
            embed = discord.Embed()
            embed.set_author(name = 'No round is currently in progress right now')
            await message.channel.send(embed = embed)
            return 

        self.passed_list.append(index)

        if len(self.passed_list) == len(self.player_list):
            self.turn = (self.turn + 1) % len(self.player_list)

            for index, channel in enumerate(self.channel_list):
                embed = discord.Embed(title = 'Everyone passed this round')
                embed.add_field(name = '\u200b', value = f'The current pot will be cleared and a new round will begin from {self.player_list[self.turn]}')
                await channel.send(embed = embed)

            self.clear_round_state()
            return

        turn = self.turn            

        while self.turn in self.passed_list:
            self.turn = (self.turn + 1) % len(self.player_list)

        for index, channel in enumerate(self.channel_list):
            embed = None
            if index == turn:
                embed = discord.Embed(title = 'You passed this round')
            else:
                embed = discord.Embed(title = f'{self.player_list[turn]} passed this round')
            embed.set_footer(text = f'{self.player_list[self.turn]} goes next')
            await channel.send(embed = embed)


    @commands.command()
    async def challenge(self, message):
        if self.game_status != 'Playing':
            embed = discord.Embed()
            embed.set_author(name = 'No game is currently in progress')
            await message.channel.send(embed = embed)
            return 

        index = self.player_list.index(message.author.name)

        if message.channel not in self.channel_list or message.channel != self.channel_list[index]:
            embed = discord.Embed()
            embed.set_author(name = 'You can only use this command in your own Bluff channel')
            await message.channel.send(embed = embed)
            return

        if self.turn != index:
            embed = discord.Embed()
            embed.set_author(name = f'Wait till your turn to play')
            await message.channel.send(embed = embed)
            return      

        if not self.round_initiated:
            embed = discord.Embed()
            embed.set_author(name = 'No round is currently in progress right now')
            await message.channel.send(embed = embed)
            return 

        previous_hand = self.current_pot[-1]

        if self.call_bluff(previous_hand):
            self.hands[(self.turn + len(self.player_list) - 1) % len(self.player_list)].extend(list(itertools.chain(*self.current_pot)))
            self.hands_notation[(self.turn + len(self.player_list) - 1) % len(self.player_list)].extend(list(itertools.chain(*self.current_pot)))
            for index, channel in enumerate(self.channel_list):
                embed = None
                if index == self.turn:
                    embed = discord.Embed(title = f'You called the bluff. {self.player_list[(self.turn + len(self.player_list) - 1) % len(self.player_list)]} will now recieve the entire pot.')
                else:
                    embed = discord.Embed(title = f'{self.player_list[self.turn]} called the bluff. {self.player_list[(self.turn + len(self.player_list) - 1) % len(self.player_list)]} will now recieve the entire pot.')
                embed.set_footer(text = f'{self.player_list[self.turn]} starts a new round')
                await channel.send(embed = embed)
        else:
            self.hands[self.turn].extend(list(itertools.chain(*self.current_pot)))
            self.hands_notation[self.turn].extend(list(itertools.chain(*self.current_pot)))
            for index, channel in enumerate(self.channel_list):
                embed = None
                if index == self.turn:
                    embed = discord.Embed(title = f'You called the bluff and missed. You will now recieve the entire pot.')
                else:
                    embed = discord.Embed(title = f'{self.player_list[self.turn]} called the bluff and missed. {self.player_list[self.turn]} will now recieve the entire pot.')
                embed.set_footer(text = f'{self.player_list[(self.turn + 1) % len(self.player_list)]} starts a new round') 
                await channel.send(embed = embed)
            self.turn = (self.turn + 1) % len(self.player_list)
        self.clear_round_state()

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
