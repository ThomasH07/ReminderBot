import discord
from discord.ext import commands
import logging
import os
from dotenv import load_dotenv
import re
import asyncio

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

# event handlers
@bot.event

async def on_ready():
   print("ReminderBot Ready!")

# able to remind a speciifc user, based on your current time to the added amount of time, also repeating, and including a message
@bot.command(name='remind')
async def remind(ctx,user: discord.User,total_seconds: str = "0",amount :int = 1,*,message: str = "",):
    global taskID
    # parses time
    try:
        delay = parse_time(total_seconds)
    except:
        await ctx.send(f"error: {ValueError}")
        return
    
    # bot making the task and adding it to the remind_list
    await ctx.send(f" I'll remind {user} in {total_seconds}.")
    task = asyncio.create_task(send_reminder(ctx,user, delay,amount,message,taskID))

    # the format of how the remind_list should be 
    remind_list[taskID] = {
        "user": user,
        "message": message,
        "amount": amount,
        "delay": delay,
        "task": task
    }
    taskID += 1
# helper function to send the reminder in discord messages based on the parsed given amount of time
async def send_reminder(ctx,user,delay,amount,message,taskID):
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
        # bot able to send all of the responses in one message rather than multiple messages
        response+=(
            f"Reminder ID: `{rid}` | User: {user} | Message: `{message}` | "
            f"Repeats: {amount}x every {delay}s\n"
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