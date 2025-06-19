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
load_dotenv()
#bot token
token = os.getenv('DISCORD_TOKEN')
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
    "EST": "America/New_York",
    "CST": "America/Chicago",
    "PST": "America/Los_Angeles",
    "CET": "Europe/Paris",
    "IST": "Asia/Kolkata",
    "JST": "Asia/Tokyo"
}

TIMEZONE_FILE = "user_timezones.json"

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
    help_text = """```
    ** THReminderBot Commands:**

    `$remind @User [HH:MM] [message] [delay] [amount]`  
    `$remind @User [message] [delay] [amount]`  
    `$remind @User [HH:MM] [message]`
    → Set a reminder for someone at a specific time or delay.

    `$settz [timezone]`  
    → Set your timezone (e.g. `$settz est`).

    `$viewReminds`  
    → View all active reminders.

    `$delete [ID]`  
    → Delete a specific reminder by ID.

    `$clear`  
    → Clear all active reminders.

    _Example:_ `$remind @Blazin 15:30 Take a break 30m 3`

    Timezones supported: `EST`, `PST`, `CET`, etc.
    Use `$settz` to update yours.
    ```"""
    await ctx.send(help_text)

# sets the user's timezone, its a requirement
@bot.command(name='settz')
async def settz(ctx, tz :str =''):
    global user_timezones
    newtz = resolve_timezone(tz)
    try:
        ZoneInfo(newtz)

        user_id = int(ctx.author.id)
        user_timezones[user_id] = tz
        save_timezones(user_timezones)
        await ctx.send(f"Your timezone has been set to `{tz}`.")
    except Exception:
        await ctx.send(" Invalid timezone. Use a format like 'est', 'cst', 'pst', 'cet', etc.'")

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
            amount = 1
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
        if amount == 0:
            remind_list.pop(taskID, None)
            return
        
    # for delay and amount parameters
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
        await ctx.send("No active reminders")
        return
    #response - list of all the active reminders
    response = "**Active Reminders:**\n"

    for rid, data in remind_list.items():
        user = data["user"]
        message = data["message"]
        amount = data["amount"]
        delay = data["delay"]
        remind_time = data["remind_time"]
        # bot able to send all of the responses in one message rather than multiple messages
        response+=(
            f"Reminder ID: `{rid}` | User: {user} | Message: `{message}` | "
            f"Repeats: {amount}x every {delay}s | remind_time: {remind_time}\n"
        )
    await ctx.send(response)

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


bot.run(token,log_handler=handler,log_level=logging.DEBUG)