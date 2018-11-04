import time
import socket
import discord
import datetime
from datetime import date
from discord.ext import commands
from enum import Enum
import asyncio
from itertools import cycle
import json
import logging
import traceback
import random
import requests
import os

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

config = {}
with open('config.json') as f:
    config = json.load(f)
description = '''Modern Day Role Play And Server Solutions Discord bot Made By Hunter L[S-24]#3037\n And the Modern Day Role Play And Sevrer Solutions Bot Development Team.'''
bot = commands.Bot(command_prefix='->', description=description)

class UptimeStatus(Enum):
    Online = 1
    Offline = 2


class UptimeMap(object):
    def __init__(self):
        self.internal_map = {}

    def reset_user(self, mid, time=None):
        self.internal_map[mid] = (UptimeStatus.Online, time)

    def logout_user(self, mid, time):
        self.internal_map[mid] = (UptimeStatus.Offline, time)

    def remove_user(self, mid):
        self.internal_map.pop(mid, None)

    def get_users_uptime(self, mid):
        return self.internal_map.get(mid, (None, None))


uptime_map = UptimeMap()

@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')
    if not hasattr(bot, 'uptime'):
        bot.uptime = datetime.datetime.utcnow()
    for server in bot.servers:
        for member in server.members:
            if member.status != discord.Status.offline:
                uptime_map.reset_user(member.id, None)

@bot.event
async def on_member_update(before, after):
    if before.status == discord.Status.offline and after.status != discord.Status.offline:
        # "Log" user in
        uptime_map.reset_user(after.id, datetime.datetime.utcnow())
    elif before.status != discord.Status.offline and after.status == discord.Status.offline:
        # "Log out" the user
        uptime_map.logout_user(after.id, datetime.datetime.utcnow())

@bot.event
async def on_member_join(member):
    uptime_map.reset_user(member.id, None)

@bot.event
async def on_member_remove(member):
    uptime_map.remove_user(member.id)

def get_bot_uptime():
    return get_human_readable_uptime_diff(bot.uptime)

def get_human_readable_user_uptime(name, mid):
    status, time = uptime_map.get_users_uptime(mid)
    if not status:
        return "I haven't seen {0} since I've been brought online.".format(name)
    status_str = 'online' if status == UptimeStatus.Online else 'offline'
    if not time:
        return "{0} has been {1} for as long as I have -- I don't know the exact details.".format(name, status_str)
    return "{0} has been {1} for {2}.".format(name, status_str, get_human_readable_uptime_diff(time))

def get_human_readable_uptime_diff(start_time):
    now = datetime.datetime.utcnow()
    delta = now - start_time
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    days, hours = divmod(hours, 24)
    if days:
        fmt = '{d} days, {h} hours, {m} minutes, and {s} seconds'
    else:
        fmt = '{h} hours, {m} minutes, and {s} seconds'
    return fmt.format(d=days, h=hours, m=minutes, s=seconds)

@bot.command()
async def uptime():
    """Tells you how long the bot has been online"""
    await bot.say('Uptime: **{}**'.format(get_bot_uptime()))

@bot.command()
async def add(left : int, right : int):
    """Adds two numbers together."""
    await bot.say(left + right)

@bot.command()
async def roll(dice : str):
    """Cmd doesnt work"""
    try:
        rolls, limit = map(int, dice.split('d'))
    except Exception:
        await bot.say('Format has to be in NdN!')
        return

    result = ', '.join(str(random.randint(1, limit)) for r in range(rolls))
    await bot.say(result)

@bot.command(pass_context=True)
@commands.has_role('Owner')
async def disconnect(ctx):
    perms = ctx.message.author.permissions_in(ctx.message.channel)
    if perms.administrator:
        await bot.say(random.choice(config['disconnect_msgs']))
        await bot.logout()
    else:
        await bot.say("You can't tell me what to do! (Administrator access is required)")

@bot.command()
async def choose(*choices : str):
    """Chooses between multiple choices."""
    await bot.say(random.choice(choices))

@bot.command(pass_context=True, description='Looks up an image from Emil\'s gallery and posts it.')
async def img(ctx, name : str):
    payload = {'q': name}
    r = requests.get(config['gallery_url'], params=payload).json()
    results = r['results']
    if results:
        author = ctx.message.author
        author_avatar_url = author.avatar_url or author.default_avatar_url
        em = discord.Embed(title=name, color=0xFFFFFF)
        em.set_author(name=author.name, icon_url=author_avatar_url)
        em.set_image(url=results[0])
        await bot.say(embed=em)
        await bot.delete_message(ctx.message)
    else:
        await bot.say('No image could be matched.', delete_after=3)

@bot.command(pass_context=True, description='Creates a new voice or text channel.')
async def create(ctx, channel_type, name):
    msg = ctx.message
    server = msg.server
    channel_type_map = {
        'text': discord.ChannelType.text,
        'voice': discord.ChannelType.voice
    }
    if channel_type not in channel_type_map:
        await bot.say('The channel type must be \"text\" or \"voice\".', delete_after=3)
        return
    everyone = discord.PermissionOverwrite()
    mine = discord.PermissionOverwrite(manage_channels=True, manage_roles=True, move_members=True)
    try:
        await bot.create_channel(msg.server, name, (server.default_role, everyone), (msg.author, mine), type=channel_type_map[channel_type])
        await bot.say('Okay {0}, created the {1} channel named \"{2}\".'.format(msg.author, channel_type, name))
    except Exception as e:
        await bot.say('Couldn\'t create the channel: {0}'.format(e))

@bot.command(pass_context=True, description='Tells you long a user has been offline or online.')
async def user_uptime(ctx, name : str):
    # convert name to mid if possible
    if ctx.message.server:
        # Not a PM
        user = ctx.message.server.get_member_named(name)
    else:
        # person pm'd the bot, so search all our servers
        user = None
        for server in bot.servers:
            user = server.get_member_named(name)
            if user:
                break
    if not user:
        await bot.say('Sorry, I couldn\'t find a user named \'{0}\'.'.format(name))
    else:
        await bot.say(get_human_readable_user_uptime(name, user.id))

@bot.command(pass_context = True)
async def clear(ctx, number):
    number = int(number) 
    counter = 0
    async for x in bot.logs_from(ctx.message.channel, limit = number):
        if counter < number:
            await bot.delete_message(x)
            counter += 1
            await asyncio.sleep(0.1)

@bot.command()
async def echo(ctx, *args):
    output = ''
    for word in args:
        output +=word
        output += ' '
    await bot.say(output)
    
@bot.command(pass_context=True, description='Gives you are discord link to the developers discord server')
async def developersdiscord(ctx):
    embed=discord.Embed(title='Modern Day Role Play And Server Solutions discord server invite', url='https://sites.google.com/view/moderndayrpand-serversolutions/about-us', description='Our Server Invite', color=0xf75301)
    embed.add_field(name='MDRPASS2018-2019 Discord invite', value='[click here to join our discord](<https://discord.gg/PnJTgnM>)', inline=True)
    embed.set_footer(text='©Modern Day Role Play And Server Solutions 2018-2019\n Made By: Developed  by Hunter L[S-24]#3037')

    await bot.say(embed=embed)

@bot.command(pass_context=True, discription='Gives you a List of High Ranking Staff for &copy MDRPASS2018')
async def staff(ctx):
    embed=discord.Embed(title='Hunters Bot',url='https://sites.google.com/view/moderndayrpand-serversolutions/about-us',color=0xf75301)
    embed.add_field(name='MDRPASS Bot Developers', value='1):Hunter L(4003)\n2): Justin B 2012', inline=True)
    embed.add_field(name='Bot-Devs From mdrpass2018', value='Lead Bot Dev Hunter L#3037\n Bot Developer Trace.k', inline=True)
    embed.set_footer(text='©Modern Day Role Play And Server Solutions 2018-2019\n Made By: Developer Hunter L[S-24]#3037 and\n trace.k')

    await bot.say(embed=embed)

@bot.command(pass_context=True, description='this is for the developer as a testing command')
async def test(ctx):
    embed=discord.Embed(title='TESTING' , description='Testing', color=0x29fffb)
    embed.set_author(name='Hunters Bot', url='https://sites.google.com/view/moderndayrpand-serversolutions/')
    embed.set_thumbnail(url='https://cdn.discordapp.com/attachments/487381473184317460/498623878122176522/San_Andreas.jpg')
    embed.add_field(name='This is a test', value='This is a test command' , inline=True)
    embed.add_field(name='Feelings', value='I liked the way your mom looked tonight' , inline=True)
    embed.add_field(name='We  will be adding a command' , value='The new command will be a new embed help command', inline=True)
    embed.add_field(name='Ben jealous ', value='Sucks democratic dick', inline=True)
    embed.set_footer(text='&copy modern day role play and server solutions \n developed by hunter l s24#3037')

    await bot.say(embed=embed)

@bot.command(pass_context=True, description='sends a ©copyright notice about the discord bot')
async def copyright(ctx):
    embed=discord.Embed(title='©Modern Day Role Play And Server Solutions copyright statement', url='https://sites.google.com/view/moderndayrpand-serversolutions/about-us', description='our copy right statement 2018-2019', color=0xfe00bf)
    embed.set_author(name='Modern Day Role Play And Server Solutions', url='https://discord.gg/3CjW3k5', icon_url='https://media.discordapp.net/attachments/497583090630131744/499752279344283648/cop100.jpeg')
    embed.add_field(name='©Copy right statement', value='Modern Day Role Play And Server Solutions License\n\nCopyright (c) 2018 Modern Day Role Play And Server Solutions \n\nPermission is hereby deined  including without limitation the rights\nto modify, merge, publish, distribute, sublicense, and/or sell\ncopies of the Software, and to permit persons to whom the Software is\nfurnished to do so, subject to the following conditions:\nTHE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR/IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\nFITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\nAUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\nLIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\nOUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\nSOFTWARE.', inline=False) 
    embed.set_footer(text='©Modern Day Role Play And Server Solutions 2018-2019\n Made By:\nHunter L[S-24]#3037')

    await bot.say(embed=embed)

@bot.command(pass_context=True, description='this is going to become the help command')
async def test2(ctx):
    embed=discord.Embed(title='©Hunters Bot', url='https://sites.google.com/view/moderndayrpand-serversolutions/about-us', color=0x1d39b5)
    embed.add_field(name='%help', value='shows this message')
    embed.add_field(name='%uptime', value='gives you the bots uptime')
    embed.add_field(name='%add', value='adds numbers like 5 5 equals 10', inline=False)
    embed.add_field(name='%create_catagory', value='command doesnt work')
    embed.add_field(name='%copyright', value='sends © copyright statement', inline=False)
    embed.add_field(name='botinvite', value='[Inivite me To Day](<https://discordapp.com/oauth2/authorize?=&client_id=452584058224902154&scope=bot&permissions=35840>)')
    embed.set_footer(text="© Modern Day Role Play And Server Solutions 2018-2019")

    await bot.say(embed=embed)
@bot.command(pass_context=True, description='Gives you the twitch link to The devs Twitx')
async def twitch(ctx):
    await bot.say('https://www.twitch.tv/midwest_hunter')
@bot.command(pass_context=True, description='this is going to become the neater help command')
async def test3(ctx):
    embed=discord.Embed(title='©Hunters Bot', url='https://sites.google.com/view/moderndayrpand-serversolutions/about-us', color=0x1d39b5)
    embed.add_field(name='%help', value='||shows this message', inline=False)
    embed.add_field(name='%uptime', value='||gives you the bots uptime')
    embed.add_field(name='%add', value='||adds numbers like 5 5 equals 10')
    embed.add_field(name='%create_catagory', value='||command doesnt work')
    embed.add_field(name='%copyright', value='||sends © copyright statement')
    embed.add_field(name='%test', value='||Give a testing embed command')
    embed.add_field(name='botinvite', value='||[Inivite me To Day](<https://discordapp.com/oauth2/authorize?=&client_id=452584058224902154&scope=bot&permissions=35840>)')
    embed.set_footer(text="© Modern Day Role Play And Server Solutions 2018-2019")

    await bot.say(embed=embed)

@bot.command(pass_context=True)
async def embed(ctx):
    embed=discord.Embed(title='Embeds', url='https://sites.google.com/view/moderndayrpand-serversolutions/', description='%embed gives you the devs embed generator', color=0xf75301)
    embed.set_author(name='Modern Day Role Play And Server Solutions', url='https://discord.gg/3CjW3k5', icon_url='https://media.discordapp.net/attachments/497583090630131744/499752279344283648/cop100.jpeg')
    embed.add_field(name='%embed' , value='[Embed Generator](<https://cog-creators.github.io/discord-embed-sandbox/>)', inline=False)
    embed.set_footer(text='©2018 Modern Day Role Play And Server Solutions')

    await bot.say(embed=embed)

@bot.command(pass_context=True)
async def test6(ctx):
    embed=discord.Embed(title='Help', url='https://sites.google.com/view/moderndayrpand-serversolutions/', description='%help gives you this message', color=0xf75301)
    embed.set_author(name='Modern Day Role Play And Server Solutions', url='https://discord.gg/3CjW3k5', icon_url='https://media.discordapp.net/attachments/497583090630131744/499752279344283648/cop100.jpeg')
    embed.add_field(name='%help' , value='Sends this message', inline=False)
    embed.add_field(name='%uptime', value='Gives you the bots uptime' , inline=False)
    embed.add_field(name='%user_uptime', value='Gives you a users uptime', inline=False)
    embed.add_field(name='%staff', value='Gives you a list of the staff that worked on this discord bots coding', inline=False)
    embed.add_field(name='%clear' , value='Clears messages only if it has the mange messages perms' , inline=False)
    embed.add_field(name='%developersdiscord', value='Gives you a embeded invite to the development discord server', inline=False)
    embed.add_field(name='%create', value='Creates a discord text channel or voice channel by doing (%create text channelname)', inline=False)
    embed.add_field(name='%echo', value='Echos a message after the echo command', inline=False)
    embed.add_field(name='%choose', value='Chooses between listed options', inline=False)
    embed.add_field(name='%add', value='adds 2 numbers together (%add 5 5)' , inline=False)
    embed.add_field(name='%twitch' , value='Sends you to the developers twitch channel', inline=False)
    embed.add_field(name='%img' , value='Command Doesnt work (devs are trying to figure out why)', inline=False)
    embed.add_field(name='%copyright' , value='Sends you Modern Day Role Play And Server Solutions Copyright Statement', inline=False)
    embed.set_footer(text='©2018 Modern Day Role Play And Server Solutions')

    await bot.say(embed=embed)
        
bot.run(config['token'])
