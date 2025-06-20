import discord
from discord.ext import commands
import logging
import os
from dotenv import load_dotenv
import re
import asyncio

import json
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta

import webserver

load_dotenv()
#bot token
token = os.getenv('DISCORD_TOKEN')
TIMEZONE_FILE = os.getenv('TIMEZONE_FILE')
# logs
handler = logging.FileHandler(filename='ReminderBot.log', encoding='utf-8',mode='w')
# server name changes, reactions 
intents = discord.Intents.default()
# read contents message
intents.message_content = True
# access members info
intents.members = True
# sets bot commands
bot = commands.Bot(command_prefix='$',intents=intents)
# hashmap of tasks 
remind_list = {}
# task IDs
taskID = 0
# timezone_aliases
timezone_aliases = {

    #North America
    "UTC": "Etc/UTC",
    "GMT": "Etc/GMT",
    "EST": "America/New_York",
    "MST": "America/Denver", 
    "CST": "America/Chicago",
    "PST": "America/Los_Angeles",
    "AKST": "America/Anchorage", 
    "HST": "Pacific/Honolulu",

    # Europe
    "CET": "Europe/Paris",
    "EET": "Europe/Athens",
    "BST": "Europe/London",
    "WET": "Europe/Lisbon",

    # Asia
    "IST": "Asia/Kolkata",
    "PKT": "Asia/Karachi",
    "WIB": "Asia/Jakarta",
    "ICT": "Asia/Bangkok", 
    "CST-CHINA": "Asia/Shanghai",
    "JST": "Asia/Tokyo",
    "KST": "Asia/Seoul", 

    # Australia & NZ
    "AWST": "Australia/Perth", 
    "ACST": "Australia/Adelaide",
    "AEST": "Australia/Sydney",
    "NZST": "Pacific/Auckland", 

    # South America
    "BRT": "America/Sao_Paulo", 
    "ART": "America/Argentina/Buenos_Aires", 
    "CLT": "America/Santiago",  

    # Africa
    "SAST": "Africa/Johannesburg",
    "WAT": "Africa/Lagos",  
    "EAT": "Africa/Nairobi",

    # Russia & Middle East
    "MSK": "Europe/Moscow",
    "AST": "Asia/Riyadh", 
    "IRST": "Asia/Tehran",         
    
}

# helper function to parse the time 
# returns the amount of time into seconds
def parse_time(str):
    # hashmap
    units = {'h': 3600, 'm': 60, 's': 1}

    # if there is one or more digits and if it matches h,m, or s
    matches = re.findall(r'(\d+)([hms])', str.lower())

    if not matches:
        raise ValueError("Invalid time format. Use formats like '1h30m'.")
    total_seconds = 0

    # amount being the given amount of time
    # unittype being either hours, minutes, or seconds
    for amount, unittype in matches:
        total_seconds += int(amount) * units[unittype]
    if total_seconds == 0:
        raise ValueError("Duration must be greater than zero.")

    return total_seconds

def resolve_timezone(alias):
    return timezone_aliases.get(alias.upper())

def load_timezones():
    if os.path.exists(TIMEZONE_FILE):
        with open(TIMEZONE_FILE, "r") as f:

            return json.load(f)
    else:
        with open(TIMEZONE_FILE, "w") as f:
            json.dump({}, f)

    return 

# Save to file
def save_timezones(data):
    with open(TIMEZONE_FILE, "w") as f:
        json.dump(data, f, indent=4)

# tries to load timezones in user time_zones, if not make it empty

user_timezones = load_timezones()
# event handlers

# checks if the user has timezone
def has_timezone(user_id, user_timezones) -> bool:
    return str(user_id) in user_timezones is not None
@bot.event

async def on_ready():
   print("ReminderBot Ready!")

# adding the help command
@bot.remove_command("help")
@bot.command(name="help")

async def help_command(ctx):
    embed = discord.Embed(
        title="THReminderBot Commands",
        description="Use the commands below to interact with the reminder system.",
        color=discord.Color.blue()
    )

    embed.add_field(
        name=" `$help`",
        value="Show all commands",
        inline=False
    )
    embed.add_field(
        name=" `$helptz`",
        value="Show all available timezone codes (e.g., `EST`, `PST`, `CET`).",
        inline=False
    )
    embed.add_field(
        name=" `$settz [timezone]`",
        value="Set your timezone (e.g. `$settz est`).",
        inline=False
    )
    embed.add_field(
        name=" `$remind @User [HH:MM] [message] [delay] [amount]`",
        value="Set a reminder for someone at a specific time or with a delay and repeat count.",
        inline=False
    )
    embed.add_field(
        name=" `$remind @User [message] [delay] [amount]`",
        value="Send a delayed, repeating reminder without a specific time.",
        inline=False
    )
    embed.add_field(
        name=" `$remind @User [HH:MM] [message]`",
        value="Set a reminder for a specific time today.",
        inline=False
    )

    embed.add_field(
        name=" `$viewReminds`",
        value="View all active reminders.",
        inline=False
    )
    embed.add_field(
        name=" `$delete [ID]`",
        value="Delete a specific reminder by its ID.",
        inline=False
    )
    embed.add_field(
        name=" `$clear`",
        value="Clear **all** your active reminders.",
        inline=False
    )

    embed.set_footer(text="Use $settz to update your timezone. See $helptz for available zones.")

    await ctx.send(embed=embed)
@bot.command(name='helptz')
async def helptz(ctx):
    tz_list = "\n".join(f"**{abbr}** → `{iana}`" for abbr, iana in timezone_aliases.items())
    
    embed = discord.Embed(
        title="🕒 Timezone Help",
        description="Use the following abbreviations with your timezone commands.",
        color=discord.Color.blue()
    )
    embed.add_field(name="Supported Timezones", value=tz_list, inline=False)
    embed.set_footer(text="Use a command like $settz EST or $time JST")

    await ctx.send(embed=embed)

# sets the user's timezone, its a requirement
@bot.command(name='settz')
async def settz(ctx, tz :str =''):
    global user_timezones
    if not tz:
        await ctx.send(" Please provide a timezone abbreviation (e.g. 'est', 'cst', 'pst', 'cet').")
        return

    newtz = resolve_timezone(tz)
    if newtz is None:
        await ctx.send(" Invalid timezone. Use a format like 'est', 'cst', 'pst', 'cet', etc.")
        return
    # validate timezone
    try:
        ZoneInfo(newtz) 
    except Exception:
        await ctx.send(" Invalid timezone. Use a format like 'est', 'cst', 'pst', 'cet', etc.'")
        return

    user_id = str(ctx.author.id)
    user_timezones[user_id] = tz
    save_timezones(user_timezones)

    await ctx.send(f"Your timezone has been set to `{tz}`.")

# able to remind a speciifc user, based on your current time to the added amount of time, also repeating, and including a message
@bot.command(name='remind')
async def remind(ctx,user: discord.User, *args):
    # no timezone set
    user_timezones = load_timezones()
    user_id = str(user.id)
    if not has_timezone(user_id,user_timezones):
        await ctx.send("user does not have a timezone, make sure to set it up using settz")
        return
    
    global taskID
    try:
        total_seconds = "0s"
        amount = 0
        message = ""
        delay = 0
        absolute_delay = None
        time = ""

        tz_name = user_timezones.get(user_id)
        user_tz = ZoneInfo(resolve_timezone(tz_name))

        # arguments allowing the command to be versatile
        if args and ":" in args[0]:
            time = args[0]
            args = args[1:]

        if len(args) >= 2:
            total_seconds = args[-2]
            amount = int(args[-1])
            message = ' '.join(args[:-2])
            delay = parse_time(total_seconds)
        elif len(args) == 1:
            message = args[0]

        # if there is a specific time detected
        if time:
            now = datetime.now(tz=user_tz)
            hour, minute = map(int, time.split(":"))
            target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target_time < now:
                target_time += timedelta(days=1)
            target_utc = target_time.astimezone(ZoneInfo("UTC"))
            now_utc = datetime.now(ZoneInfo("UTC"))
            absolute_delay = (target_utc - now_utc).total_seconds()
        else:
            absolute_delay = None 
        remind_time = datetime.now(user_tz) + timedelta(seconds=(absolute_delay or delay))
        formatted_time = remind_time.strftime('%Y-%m-%d %H:%M:%S %Z')

    except Exception as e:
        await ctx.send(f"error: {e}")
        return
    
    if(total_seconds != "0s"):
        await ctx.send(f" I'll remind {user} at `{formatted_time}` ({tz_name}) and after repeats X total seconds:{amount} X {total_seconds}")
    else:
        await ctx.send(f" I'll remind {user} at `{formatted_time}` ({tz_name}).")

    # bot making the task and adding it to the remind_list
    task = asyncio.create_task(send_reminder(ctx,user, delay,amount,message,taskID,absolute_delay))

    # the format of how the remind_list should be 
    remind_list[taskID] = {
        "user": user,
        "message": message,
        "amount": amount,
        "delay": delay,
        "task": task,
        "remind_time": remind_time
    }
    taskID += 1

# helper function to send the reminder in discord messages based on the parsed given amount of time
async def send_reminder(ctx,user,delay,amount,message,taskID,absolute_delay):
    # if there is a specific time
    if absolute_delay:
        await asyncio.sleep(absolute_delay)
        reminder = remind_list.get(taskID)
        if not reminder:
            return
        await ctx.send(f"Reminder for {user.mention}: {message}")

        # if there is no repeats
        
    # for delay and amount parameters
    if not absolute_delay:
        amount += 1
    for i in range(amount):
        await asyncio.sleep(delay)
        reminder = remind_list.get(taskID)
        if not reminder:
            return
        await ctx.send(f"Reminder for {user.mention}: {message}")
    remind_list.pop(taskID, None)

# allows you to view all the available reminders for all users
@bot.command(name='viewReminds')
async def viewReminds(ctx):
    if not remind_list:
        await ctx.send(" No active reminders.")
        return

    embed = discord.Embed(
        title=" Active Reminders",
        description="Here's a list of all currently active reminders:",
        color=discord.Color.blue()
    )

    for rid, data in remind_list.items():
        user = data["user"]
        message = data["message"]
        amount = data["amount"]
        delay = data["delay"]
        remind_time = data["remind_time"]

        embed.add_field(
            name=f"Reminder ID: {rid}",
            value=(
                f" **User:** {user}\n"
                f" **Message:** `{message}`\n"
                f" **Repeats:** {amount}x every {delay}s\n"
                f" **Next Reminder:** {remind_time}\n"
            ),
            inline=False
        )

    await ctx.send(embed=embed)

# allows you to delete a specific reminder that is not needed
@bot.command(name='delete')
async def delete(ctx,taskID: int):
    reminder = remind_list.get(taskID)

    if not reminder:
        await ctx.send("No active reminders")
        return
    
    task = reminder.get("task")

    if task:
        task.cancel()

    remind_list.pop(taskID, None)    
    await ctx.send(f"successfully deleted task {taskID}")

#clears all the reminders
@bot.command(name='clear')
async def clear(ctx):
    for rid, data in remind_list.items():
        task = data["task"]
        task.cancel()
    remind_list.clear()
    await ctx.send("successfully cleared all tasks")

webserver.keep_alive()
bot.run(token,log_handler=handler,log_level=logging.DEBUG)