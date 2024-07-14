from typing import Final
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler, CallbackQueryHandler, ContextTypes
from telegram.error import TimedOut
# new added features scheduling 
from telegram_bot_calendar import DetailedTelegramCalendar, LSTEP
import calendar
# from datetime import datetime
from datetime import datetime, timedelta, time
# from datetime import timedelta
from database import Database
from html import escape
import textwrap
import time as tm
import re
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import asyncio
import pytz
import asyncio
import signal
import sys

# # Setup basic logging
# logging.basicConfig(level=logging.DEBUG)
# logger = logging.getLogger(__name__)

TOKEN: Final = '6729973842:AAH8XIUZ_fMl1WdAlkdGnD1zOlyyZmC0ZCI'
BOT_USERNAME: Final = '@chat_lah_bot'
MAX_RETRIES = 3  # Maximum number of retries
WAITING_FOR_DESCRIPTION = 1
# REMINDER_TIME_STATE = 1  # State for conversation handler

class TelegramBot:
    def __init__(self, token, bot_username):
        self.token = token
        self.bot_username = bot_username
        self.db = self.connect_to_database()
        self.application = self.connect_to_telegram()
        self.last_callback_time = None
        self.application.add_handler(CallbackQueryHandler(self.toggle_view, pattern='^toggle_details$'))
        self.scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Kuala_Lumpur'))
        self.scheduler.add_job(self.check_and_send_reminders, 'interval', minutes=1)
        self.scheduler.start()

        self.month_to_number = {
            'January': 1, 'February': 2, 'March': 3, 'April': 4,
            'May': 5, 'June': 6, 'July': 7, 'August': 8,
            'September': 9, 'October': 10, 'November': 11, 'December': 12
        }

    def connect_to_telegram(self):
        for attempt in range(MAX_RETRIES):
            try:
                application = ApplicationBuilder().token(self.token).build()
                return application
            except TimedOut:
                print(f"Connection attempt {attempt+1} timed out. Retrying...")
                tm.sleep(2)  # Wait 2 seconds before retrying
        raise Exception("Failed to connect to Telegram API after retries")

    def connect_to_database(self):
        try:
            # return Database(host="localhost", user="root", password="", database="telegram_bot_db")
            return Database(host="mychatlahbotserver.mysql.database.azure.com", user="sheila@mychatlahbotserver", password="JoelLim1212!", database="telegram_bot_db")
        except ConnectionError as e:
            print(e)
            raise

    async def start_command(self, update: Update, context: CallbackContext):
        await update.message.reply_text('Hello! Thanks for choosing me as your buddy, and feel free to chat with me as I am ChatLah!')

    def convert_string_to_time(time_str):
        try:
            return datetime.strptime(time_str, "%H:%M:%S").time()
        except ValueError:
            return None  # or handle the error appropriately

    def format_time_or_duration(self, value):
        if isinstance(value, timedelta):
            total_seconds = int(value.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours:02d}:{minutes:02d}"
        elif isinstance(value, time):
            return value.strftime('%H:%M')
        elif value is None:
            return "Not Set"
        else:
            print(f"Unexpected type {type(value)}: {value}")
            return "Format Error"
        
    # # Define the function in your bot code
    # def parse_search_query(self, search_term):
    #     if 'date:' in search_term:
    #         date_part = search_term.split('date:')[1].strip()
    #         return 'date', date_part
    #     elif 'time:' in search_term:
    #         time_part = search_term.split('time:')[1].strip()
    #         return 'time', time_part
    #     else:
    #         return 'keyword', search_term

    # async def help_command(self, update: Update, context: CallbackContext):
    #     await update.message.reply_text('I am ChatLah! Please type anything so I can respond!')

    async def help_command(self, update: Update, context: CallbackContext):
        help_text = """
    Hello! I'm ChatLah, your task management assistant. Here are some commands you can use:

    - /start: Start interacting with me.
    - /help: Display this help message.
    - /create [description]: Create a new task with a description.
    - /list: List all your current tasks.
    - /delete [task_id]: Delete a specific task.
    - /status [task_id]: Update the status of a specific task.
    - /set_due_date [task_id]: Set the due date for a specific task.
    - /set_due_time [task_id]: Set the due time for a specific task.
    - /search [keywords]: Search tasks by keywords in the description.
    - /search_full_details: Show the full details for the  task. 
    - /remind [task_id]: Set a reminder for a specific task.
    """
        await update.message.reply_text(help_text)

    async def custom_command(self, update: Update, context: CallbackContext):
        await update.message.reply_text('This is custom command!')

    async def create_task_command(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        description = ' '.join(context.args) if context.args else None
        if not description:
            await update.message.reply_text("Please provide a task description. E.g., /create Finish task")
            return

        task_id = self.db.create_task(user_id, description)
        if task_id:
            print(f"Task {task_id} created successfully.")
            await update.message.reply_text(f"Task created: {description}")
        else:
            print("Failed to create task due to database error.")
            await update.message.reply_text("Failed to create task. Please try again.")

    async def process_task_description(self, update: Update, context: CallbackContext, description: str):
        user_id = update.message.from_user.id
        print(f"Creating task for user {user_id} with description '{description}'")  # Debugging output
        task_id = self.db.create_task(user_id, description)
        if task_id:
            await update.message.reply_text(f"Task created: {description} (ID: {task_id})")
        else:
            await update.message.reply_text("Failed to create task. Please try again.")
        return ConversationHandler.END

    async def handle_description(self, update: Update, context: CallbackContext):
        description = update.message.text
        await self.process_task_description(update, context, description)
        return ConversationHandler.END

    async def list_tasks_command(self, message_or_update, context: CallbackContext):
        if isinstance(message_or_update, Update):
            message = message_or_update.message
        else:
            message = message_or_update

        user_id = message.from_user.id
        tasks = self.db.list_tasks(user_id)  # Ensure this fetches only active, non-deleted tasks.
        if not tasks:
            await message.reply_text("You have no tasks.")
            return

        detailed_view = context.user_data.get('detailed_view', False)

        # Define column widths
        id_width = 4
        description_width = 30
        status_width = 12
        date_width = 10
        time_width = 8

        headers = f"{'ID':<{id_width}} | {'Description':<{description_width}} | {'Status':<{status_width}}"
        if detailed_view:
            headers += f" | {'Due Date':<{date_width}} | {'Due Time':<{time_width}}"
        separators = '-' * len(headers)

        lines = [headers, separators]

        task_map = {}
        for idx, task in enumerate(tasks, 1):
            task_id, description, status, due_date, due_time = task
            due_date_display = due_date.strftime('%Y-%m-%d') if due_date else "No Date"
            due_time_display = self.format_time_or_duration(due_time) if due_time else "No Time"
            
            wrapped_description = textwrap.wrap(description, width=description_width)

            for i, desc_line in enumerate(wrapped_description):
                if i == 0:
                    line = f"{idx:<{id_width}} | {desc_line:<{description_width}} | {status:<{status_width}}"
                    if detailed_view:
                        line += f" | {due_date_display:<{date_width}} | {due_time_display:<{time_width}}"
                else:
                    line = f"{'':<{id_width}} | {desc_line:<{description_width}} | {'':<{status_width}}"
                    if detailed_view:
                        line += f" | {'':<{date_width}} | {'':<{time_width}}"
                lines.append(line)
            
            lines.append(separators)  # Separate each entry
            task_map[str(idx)] = task_id  # Map displayed ID to internal ID

        # Store the mapping in user data
        context.user_data['task_map'] = task_map

        task_list = "\n".join(lines)
        toggle_button_text = "Show More Details >>" if not detailed_view else "<< Show Less Details"
        toggle_button = InlineKeyboardButton(toggle_button_text, callback_data="toggle_details")
        reply_markup = InlineKeyboardMarkup([[toggle_button]])

        await message.reply_text(f"<pre>{task_list}</pre>", reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        instruction_text = "Use /delete [task_id] to delete a task, /status [task_id] to update a task status. For more commands, type /help."
        await message.reply_text(instruction_text)

    async def toggle_view(self, update: Update, context: CallbackContext):
        query = update.callback_query
        if not query:
            print("No callback query found.")
            return

        await query.answer()  # Acknowledge the callback query to stop the loading spinner on the button

        # Toggle the detailed view state in the user context
        context.user_data['detailed_view'] = not context.user_data.get('detailed_view', False)
        tasks = self.db.list_tasks(query.from_user.id)  # Assumes list_tasks only returns non-deleted tasks

        # Define column widths
        id_width = 4
        description_width = 30
        status_width = 12
        date_width = 10
        time_width = 8

        headers = f"{'ID':<{id_width}} | {'Description':<{description_width}} | {'Status':<{status_width}}"
        if context.user_data['detailed_view']:
            headers += f" | {'Due Date':<{date_width}} | {'Due Time':<{time_width}}"
        separators = '-' * len(headers)

        lines = [headers, separators]

        task_map = {}
        for idx, task in enumerate(tasks, 1):
            task_id, description, status, due_date, due_time = task
            due_date_display = due_date.strftime('%Y-%m-%d') if due_date else "No Date"
            due_time_display = self.format_time_or_duration(due_time) if due_time else "No Time"
            
            wrapped_description = textwrap.wrap(description, width=description_width)

            for i, desc_line in enumerate(wrapped_description):
                if i == 0:
                    line = f"{idx:<{id_width}} | {desc_line:<{description_width}} | {status:<{status_width}}"
                    if context.user_data['detailed_view']:
                        line += f" | {due_date_display:<{date_width}} | {due_time_display:<{time_width}}"
                else:
                    line = f"{'':<{id_width}} | {desc_line:<{description_width}} | {'':<{status_width}}"
                    if context.user_data['detailed_view']:
                        line += f" | {'':<{date_width}} | {'':<{time_width}}"
                lines.append(line)
            
            lines.append(separators)  # Separate each entry
            task_map[str(idx)] = task_id  # Map displayed ID to internal ID

        # Store the mapping in user data
        context.user_data['task_map'] = task_map

        task_list = "\n".join(lines)
        toggle_button_text = "Show More Details >>" if not context.user_data['detailed_view'] else "<< Show Less Details"
        toggle_button = InlineKeyboardButton(toggle_button_text, callback_data="toggle_details")
        reply_markup = InlineKeyboardMarkup([[toggle_button]])

        # Use edit_message_text to update the existing message
        if query.message:
            try:
                await query.edit_message_text(text=f"<pre>{task_list}</pre>", reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            except Exception as e:
                print(f"Error while updating task list: {str(e)}")
        else:
            print("No message found in query to update.")

    async def choose_task_status(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()

        task_id = int(query.data.split('_')[1])
        context.user_data['task_id'] = task_id

        statuses = ["Incomplete", "In Progress", "Complete", "Deferred", "Cancelled"]
        buttons = [
            [InlineKeyboardButton(status, callback_data=f"set_status_{status.replace(' ', '_')}_{task_id}")]
            for status in statuses
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.edit_message_text(text="Choose task status:", reply_markup=reply_markup)

    async def bulk_update_status_command(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()

        statuses = ["Incomplete", "In Progress", "Complete", "Deferred", "Cancelled"]
        buttons = [
            [InlineKeyboardButton(status, callback_data=f"bulk_set_{status.replace(' ', '_').lower()}")]
            for status in statuses
        ]
        await query.edit_message_text(
            "Select a status to apply to all tasks:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    async def set_bulk_task_status(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()

        data = query.data.split('_')  # Expected format "bulk_set_{status}"
        status = ' '.join(data[2:])  # Convert status back from 'bulk_set_completed' to 'Completed'

        user_id = update.effective_user.id
        success = self.db.update_all_tasks_status(user_id, status)
        if success:
            await query.message.reply_text(f"All tasks updated to {status}.")
        else:
            await query.message.reply_text("Failed to update all tasks. Please try again.")

    async def set_task_status(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()

        data = query.data.split('_')  # Expected format "set_status_{status}_{task_id}"
        if len(data) < 4:
            await query.message.reply_text("Invalid data format.")
            return

        # Reconstruct the status with spaces if needed
        status = '_'.join(data[2:-1]).replace('_', ' ')
        task_id = int(data[-1])
        user_id = query.from_user.id

        success = self.db.update_task_status(user_id, task_id, status)
        if success:
            await query.message.reply_text(f"Task {task_id} status updated to {status}.")
        else:
            await query.message.reply_text("Failed to update task status. Please try again.")

    # async def delete_task_command(self, update: Update, context: CallbackContext):
    #     user_id = update.message.from_user.id
    #     if len(context.args) == 0:
    #         await update.message.reply_text("Please provide a task ID to delete. Usage: /delete [task_id]")
    #         return
    #     try:
    #         task_id = int(context.args[0])
    #     except ValueError:
    #         await update.message.reply_text("Invalid task ID. Please provide a numeric task ID.")
    #         return

    #     if self.db.delete_task(user_id, task_id):
    #         await update.message.reply_text(f"Task {task_id} deleted.")
    #     else:
    #         await update.message.reply_text(f"Failed to delete task {task_id}.")

    async def delete_task_command(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        if len(context.args) == 0:
            await update.message.reply_text("Please provide a task ID to delete. Usage: /delete [task_id]")
            return

        try:
            current_user_task_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Invalid task ID. Please provide a numeric task ID.")
            return

        if self.db.delete_task(user_id, current_user_task_id):
            await update.message.reply_text(f"Task {current_user_task_id} deleted.")
        else:
            await update.message.reply_text(f"Failed to delete task {current_user_task_id}.")

    # unable to double confirm with user when delete 
    # async def delete_task_command(self, update: Update, context: CallbackContext):
    #     user_id = update.message.from_user.id
    #     if len(context.args) == 0:
    #         await update.message.reply_text("Please provide a task ID to delete. Usage: /delete [task_id]")
    #         return

    #     try:
    #         current_user_task_id = int(context.args[0])
    #     except ValueError:
    #         await update.message.reply_text("Invalid task ID. Please provide a numeric task ID.")
    #         return

    #     # Fetch the task details to verify and display before deletion
    #     task_details = self.db.get_task_details_by_current_user_task_id(user_id, current_user_task_id)
    #     if not task_details or task_details['is_deleted']:
    #         await update.message.reply_text("Invalid task number or task already deleted.")
    #         return

    #     if 'status' not in task_details:
    #         await update.message.reply_text("Task status information is missing.")
    #         return

    #     # Prepare confirmation message with task details
    #     task_info = f"Description: {task_details['description']}\nStatus: {task_details['status']}\nDue Date: {task_details['due_date'].strftime('%Y-%m-%d') if task_details['due_date'] else 'Not Set'}\nDue Time: {task_details['due_time'] if task_details['due_time'] else 'Not Set'}"
    #     confirmation_text = f"Are you sure you want to delete this task? This action cannot be undone.\n\n{task_info}"
    #     buttons = [
    #         InlineKeyboardButton("Confirm", callback_data=f"confirm_delete_{current_user_task_id}"),
    #         InlineKeyboardButton("Cancel", callback_data="cancel_delete")
    #     ]
    #     await update.message.reply_text(confirmation_text, reply_markup=InlineKeyboardMarkup([[buttons[0], buttons[1]]]))

    # async def handle_task_deletion_confirmation(self, update: Update, context: CallbackContext):
    #     query = update.callback_query
    #     await query.answer()

    #     data = query.data.split('_')
    #     if len(data) < 3:
    #         await query.edit_message_text(text="Error: Invalid operation data received.")
    #         return

    #     if data[0] == "confirm" and data[1] == "delete":
    #         current_user_task_id = int(data[2])
    #         try:
    #             if self.db.delete_task(query.from_user.id, current_user_task_id):
    #                 await query.edit_message_text(text=f"Task {current_user_task_id} has been successfully deleted.")
    #             else:
    #                 await query.edit_message_text(text="Failed to delete the task. It might have already been deleted.")
    #         except Exception as e:
    #             await query.edit_message_text(text=f"An error occurred: {str(e)}")
    #     elif data[0] == "cancel":
    #         await query.edit_message_text(text="Task deletion cancelled.")

    async def status_task_command(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        tasks = self.db.list_tasks(user_id)
        if not tasks:
            await update.message.reply_text("You have no tasks.")
            return

        buttons = [
            [InlineKeyboardButton(f"{task[0]}. {task[1]} ({task[2]})", callback_data=f"status_{task[0]}")]
            for task in tasks
        ]
        # Add a button for bulk update
        buttons.append([InlineKeyboardButton("Bulk Update All Tasks", callback_data="bulk_update_status")])

        await update.message.reply_text(
            "Select a task to update its status or choose to bulk update all tasks:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # Updated set_due_date_command in capstone2.py
    async def set_due_date_command(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        if len(context.args) == 0:
            await update.message.reply_text("Please provide a task ID. Usage: /set_due_date [task_id]")
            return
        try:
            current_user_task_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Invalid task ID. Please provide a numeric task ID.")
            return

        # Get the task details to verify the task exists and is not deleted
        task_details = self.db.get_task_details(user_id, current_user_task_id)
        if not task_details or task_details['is_deleted']:
            await update.message.reply_text("Task not found or it has been deleted.")
            return

        context.user_data['current_user_task_id_for_due_date'] = current_user_task_id  # Save current_user_task_id

        # Trigger the selection of a year when /set_due_date is called
        buttons = [[InlineKeyboardButton(str(year), callback_data=f"year_{year}")] for year in range(datetime.now().year, datetime.now().year + 5)]
        await update.message.reply_text("Please choose a year:", reply_markup=InlineKeyboardMarkup(buttons))

    async def handle_due_date_selection(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        current_user_task_id = context.user_data.get('current_user_task_id_for_due_date')

        # Get the task details
        task_details = self.db.get_task_details_by_current_user_task_id(user_id, current_user_task_id)
        if not task_details or task_details['is_deleted']:
            await query.message.reply_text(text="Task not found or has been deleted.")
            return

        print(f"Using task with current_user_task_id {current_user_task_id} for due date setting")  # Debugging output

        # Call or write a function to display the calendar here
        await self.prompt_calendar_for_due_date(update, context)

    # Updated handle_year_selection function in capstone2.py
    async def handle_year_selection(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()
        selected_year = int(query.data.split('_')[1])
        context.user_data['selected_year'] = selected_year
        await self.handle_early_half_year_selection(update, context)

    # Updated handle_early_half_year_selection function in capstone2.py
    async def handle_early_half_year_selection(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()
        month_buttons = [
            [InlineKeyboardButton(month, callback_data=f"month_{month}")]
            for month in ['January', 'February', 'March', 'April', 'May', 'June']
        ]
        month_buttons.append([InlineKeyboardButton("Next →", callback_data="previous_months")])
        await query.edit_message_text(
            text="Please choose a month:",
            reply_markup=InlineKeyboardMarkup(month_buttons)
        )

    # Updated handle_late_half_year_selection function in capstone2.py
    async def handle_late_half_year_selection(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()

        month_buttons = [
            [InlineKeyboardButton(month, callback_data=f"month_{month}")]
            for month in ['July', 'August', 'September', 'October', 'November', 'December']
        ]
        month_buttons.append([InlineKeyboardButton("← Back", callback_data="next_months")])

        await query.edit_message_text(
            text="Please choose a month:",
            reply_markup=InlineKeyboardMarkup(month_buttons)
        )

    # Updated handle_month_selection function in capstone2.py
    async def handle_month_selection(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()

        month_name = query.data.split('_')[1]  # Extracting the month name from callback data.
        selected_month = self.month_to_number[month_name]
        context.user_data['selected_month'] = selected_month

        year = context.user_data.get('selected_year', datetime.now().year)
        days_in_month = calendar.monthrange(year, selected_month)[1]

        # Create day buttons and arrange them in a grid.
        day_buttons = []
        for day in range(1, days_in_month + 1):
            day_buttons.append(InlineKeyboardButton(str(day), callback_data=f"day_{day}"))

        # Organizing buttons in a grid of 5 columns.
        grid_buttons = [day_buttons[i:i + 5] for i in range(0, len(day_buttons), 5)]

        await query.edit_message_text(
            text=f"Please choose a day in {month_name}:",
            reply_markup=InlineKeyboardMarkup(grid_buttons)
        )

    # Updated handle_day_selection function in capstone2.py
    async def handle_day_selection(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()

        if 'selected_month' not in context.user_data or 'selected_year' not in context.user_data:
            await query.message.reply_text(text="Please select a month first.")
            return

        if query.data.startswith('day_'):
            day_selected = int(query.data.split('_')[1])
            month = context.user_data['selected_month']
            year = context.user_data['selected_year']
            # Format the date in YYYY-MM-DD format
            formatted_date = f"{year}-{month:02d}-{day_selected:02d}"
            user_id = update.effective_user.id

            # Retrieve current_user_task_id stored previously in user data
            current_user_task_id = context.user_data.get('current_user_task_id_for_due_date')

            # Debugging output to ensure correct task ID is being used
            print(f"Setting due date for current_user_task_id: {current_user_task_id}")

            # Call the method to set due date in the database
            success, message = self.db.set_task_due_date(user_id, current_user_task_id, formatted_date)
            if success:
                if message:
                    await query.message.reply_text(f"The due date is already set to {formatted_date} for task ID {current_user_task_id}.")
                else:
                    await query.message.reply_text(f"Due date set to {formatted_date} for task ID {current_user_task_id}.")
            else:
                await query.message.reply_text(f"Failed to set due date. {message if message else 'Please try again.'}")
        else:
            await query.message.reply_text("Invalid day selection.")

    # No changes needed for prompt_calendar_for_due_date in capstone2.py
    async def prompt_calendar_for_due_date(self, update: Update, context: CallbackContext):
        buttons = [[InlineKeyboardButton(str(year), callback_data=f"year_{year}")] for year in range(datetime.now().year, datetime.now().year + 5)]
        await update.message.reply_text("Please choose a year:", reply_markup=InlineKeyboardMarkup(buttons))

    # Updated set_due_time_command in capstone2.py
    async def set_due_time_command(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        if len(context.args) == 0:
            await update.message.reply_text("Please provide a task ID. Usage: /set_due_time [task_id]")
            return

        current_user_task_id = int(context.args[0])
        task = self.db.get_task_details(user_id, current_user_task_id)
        if not task:
            await update.message.reply_text("Task does not exist.")
            return
        if task['is_deleted']:
            await update.message.reply_text("This task has been deleted and cannot be modified.")
            return

        context.user_data['current_user_task_id_for_due_time'] = current_user_task_id

        # # Organize hours into two rows: 1-6 and 7-12
        # buttons = [
        #     [InlineKeyboardButton(f"{i:02d}", callback_data=f"hour_{i:02d}") for i in range(1, 7)],
        #     [InlineKeyboardButton(f"{i:02d}", callback_data=f"hour_{i:02d}") for i in range(7, 13)]
        # ]
        # await update.message.reply_text("Please choose an hour:", reply_markup=InlineKeyboardMarkup(buttons))

        # Organize hours into more rows for a full day: 0-23
        buttons = [
            [InlineKeyboardButton(f"{i:02d}", callback_data=f"hour_{i:02d}") for i in range(0, 6)],
            [InlineKeyboardButton(f"{i:02d}", callback_data=f"hour_{i:02d}") for i in range(6, 12)],
            [InlineKeyboardButton(f"{i:02d}", callback_data=f"hour_{i:02d}") for i in range(12, 18)],
            [InlineKeyboardButton(f"{i:02d}", callback_data=f"hour_{i:02d}") for i in range(18, 24)]
        ]
        await update.message.reply_text("Please choose an hour:", reply_markup=InlineKeyboardMarkup(buttons))

    # Updated handle_hour_selection in capstone2.py
    async def handle_hour_selection(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()

        hour = int(query.data.split('_')[1])
        context.user_data['selected_hour'] = hour

        # Prompt for minute selection, ensuring all minute options are displayed
        minute_buttons = [
            InlineKeyboardButton(f"{i:02d}", callback_data=f"minute_{i:02d}") for i in range(0, 60, 5)
        ]
        # Creating rows of 6 buttons each for minutes
        keyboard_layout = [minute_buttons[i:i + 6] for i in range(0, len(minute_buttons), 6)]
        await query.edit_message_text(text="Please choose minutes:", reply_markup=InlineKeyboardMarkup(keyboard_layout))

    # Updated handle_minute_selection in capstone2.py
    async def handle_minute_selection(self, update: Update, context: CallbackContext):
        query = update.callback_query
        if query:
            await query.answer()

        minute = int(query.data.split('_')[1])
        hour = context.user_data['selected_hour']
        time_str = f"{hour:02d}:{minute:02d}"
        current_user_task_id = context.user_data['current_user_task_id_for_due_time']
        task = self.db.get_task_details(update.effective_user.id, current_user_task_id)

        if not task:
            await query.message.reply_text("Task no longer exists.")
            return
        if task['is_deleted']:
            await query.message.reply_text("This task has been deleted and cannot be modified.")
            return
        
        # Update the task due time in the database
        if self.db.set_task_due_time(update.effective_user.id, current_user_task_id, time_str):
            # Send a new message instead of editing the current one
            await query.message.reply_text(f"Due time set to {time_str} for task ID {current_user_task_id}.")
        else:
            await query.message.reply_text("Failed to set due time. Please try again.")

    # # Handle period selection
    # async def handle_period_selection(self, update: Update, context: CallbackContext):
    #     query = update.callback_query
    #     if query:
    #         await query.answer()

    #     period = query.data.split('_')[1]
    #     hour = context.user_data['selected_hour']
    #     if period == "PM" and hour != 12:
    #         hour += 12
    #     elif period == "AM" and hour == 12:
    #         hour = 0
    #     minute = context.user_data['selected_minute']

    #     time_str = f"{hour:02d}:{minute:02d}:00"
    #     user_id = query.from_user.id
    #     current_user_task_id = context.user_data['current_user_task_id_for_due_time']

    #     task_details = self.db.get_task_details(user_id, current_user_task_id)
    #     if not task_details or task_details['is_deleted']:
    #         await query.message.reply_text("This task has been deleted and cannot be modified.")
    #         return

    #     if self.db.set_task_due_time(user_id, current_user_task_id, time_str):
    #         await query.message.reply_text(f"Due time set for task ID {current_user_task_id}.")
    #     else:
    #         await query.message.reply_text("Failed to set due time. Please try again.")

    # # new code added 10 July 2024 - search
    # async def search_tasks_command(self, update: Update, context: CallbackContext):
    #     if not context.args:
    #         await update.message.reply_text("Please provide a search term. Usage: /search [keywords|date: YYYY-MM-DD|time: HH]")
    #         return

    #     search_term = ' '.join(context.args).lower()  # Combines all arguments into a single string and makes it lowercase
    #     search_type, search_value = self.parse_search_query(search_term)  # Correct call to the function
    #     user_id = update.message.from_user.id
    #     matching_tasks = self.db.search_tasks(user_id, search_type, search_value)  # Assuming this function is correctly implemented

    #     if not matching_tasks:
    #         await update.message.reply_text("No tasks found matching your criteria.")
    #         return

    #     response_text = "Here are the tasks matching your search:\n\n"
    #     response_text += "\n".join(
    #         f"{task['current_user_task_id']}. {task['description']} (Status: {task['status']}, Date: {task['due_date']})"
    #         for task in matching_tasks
    #     )

    #     await update.message.reply_text(response_text)

    async def search_full_task_details_command(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        tasks = self.db.search_tasks_full_details(user_id)
        if not tasks:
            await update.message.reply_text("No tasks with a due date set.")
            return

        response_text = "Tasks with a due date:\n\n" + "\n".join(
            f"{task['current_user_task_id']}. {task['description']} (Status: {task['status']}, Due Date: {task['due_date'].strftime('%Y-%m-%d')})"
            for task in tasks
        )
        await update.message.reply_text(response_text)

    async def search_tasks_command(self, update: Update, context: CallbackContext):
        if not context.args:
            await update.message.reply_text("Please provide a search term. Usage: /search [keywords]")
            return

        search_term = ' '.join(context.args).lower()  # Combines all arguments into a single string and makes it lowercase
        user_id = update.message.from_user.id
        matching_tasks = self.db.search_tasks_by_description(user_id, search_term)

        if not matching_tasks:
            await update.message.reply_text("No tasks found matching your criteria.")
            return

        response_text = "Here are the tasks matching your search:\n\n" + "\n".join(
            f"{task['current_user_task_id']}. {task['description']} (Status: {task['status']})"
            for task in matching_tasks
        )
        await update.message.reply_text(response_text)

    # new code for reminder 10 july 2024
    async def set_reminder_command(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        tasks = self.db.list_tasks_for_reminders(user_id)
        if not tasks:
            await update.message.reply_text("You have no tasks with due dates set to set reminders for.")
            return
        
        buttons = [
            [InlineKeyboardButton(f"{task['current_user_task_id']}. {task['description']}", callback_data=f"set_reminder_{task['current_user_task_id']}")]
            for task in tasks
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await update.message.reply_text("Select a task to set a reminder:", reply_markup=reply_markup)

    # async def handle_set_reminder(self, update: Update, context: CallbackContext):
    #     query = update.callback_query
    #     await query.answer()

    #     task_id = int(query.data.split('_')[2])
    #     task_details = self.db.get_current_user_task_id_from_tasks(task_id)
        
    #     if not task_details:
    #         await query.edit_message_text(text="Task details could not be fetched.")
    #         return

    #     context.user_data['selected_task_id_for_reminder'] = task_id
    #     context.user_data['current_user_task_id_for_reminder'] = task_details.get('current_user_task_id')

    #     if context.user_data['current_user_task_id_for_reminder'] is None:
    #         await query.edit_message_text(text="No current user task ID available for this task.")
    #         return

    #     buttons = [
    #         [InlineKeyboardButton("5 minutes before", callback_data="reminder_time_5_minutes")],
    #         [InlineKeyboardButton("10 minutes before", callback_data="reminder_time_10_minutes")],
    #         [InlineKeyboardButton("15 minutes before", callback_data="reminder_time_15_minutes")],
    #         [InlineKeyboardButton("30 minutes before", callback_data="reminder_time_30_minutes")],
    #         [InlineKeyboardButton("1 hour before", callback_data="reminder_time_60_minutes")],
    #         [InlineKeyboardButton("1 day before", callback_data="reminder_time_1440_minutes")],
    #         [InlineKeyboardButton("Custom...", callback_data="reminder_time_custom")]
    #     ]
    #     reply_markup = InlineKeyboardMarkup(buttons)
    #     await query.edit_message_text(text="Select a reminder time:", reply_markup=reply_markup)

    async def handle_set_reminder(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        task_id = int(query.data.split('_')[2])
        task_details = self.db.get_current_user_task_id_from_tasks(user_id, task_id)
        
        if not task_details:
            await query.edit_message_text(text="Task details could not be fetched.")
            return

        due_date = task_details.get('due_date')
        due_time = task_details.get('due_time')

        if not due_date:
            await query.message.reply_text(text="Please set a due date before proceeding to set a reminder. Use /set_due_date [task_id]")
            return

        if due_time is None:
            due_time_str = "Not Set"
        else:
            if isinstance(due_time, timedelta):
                due_time = (datetime.min + due_time).time()
            due_time_str = due_time.strftime("%H:%M:%S")

        context.user_data['selected_task_id_for_reminder'] = task_id
        context.user_data['current_user_task_id_for_reminder'] = task_details.get('current_user_task_id')

        buttons = [
            [InlineKeyboardButton("5 minutes before", callback_data="reminder_time_5_minutes")],
            [InlineKeyboardButton("10 minutes before", callback_data="reminder_time_10_minutes")],
            [InlineKeyboardButton("15 minutes before", callback_data="reminder_time_15_minutes")],
            [InlineKeyboardButton("30 minutes before", callback_data="reminder_time_30_minutes")],
            [InlineKeyboardButton("1 hour before", callback_data="reminder_time_60_minutes")],
            [InlineKeyboardButton("1 day before", callback_data="reminder_time_1440_minutes")],
            [InlineKeyboardButton("Custom...", callback_data="reminder_time_custom")]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)

        await query.message.reply_text(
            text=f"Task {task_id} due date is: {due_date} and due time is: {due_time_str}\nPlease select a reminder time:",
            reply_markup=reply_markup
        )

        # Remove the reminder selection buttons
        await query.message.delete()

    # async def handle_reminder_time_selection(self, update: Update, context: CallbackContext):
    #     query = update.callback_query
    #     await query.answer()

    #     data = query.data.split('_')
    #     if data[2] == 'custom':
    #         # If the user selects custom, handle that separately
    #         await query.edit_message_text(text="Enter custom reminder time in the format: 'X minutes/hours/days/weeks before'")
    #         context.user_data['awaiting_custom_reminder_input'] = True
    #     else:
    #         reminder_time_minutes = int(data[2])
    #         task_id = context.user_data['selected_task_id_for_reminder']
    #         current_user_task_id = context.user_data['current_user_task_id_for_reminder']
    #         user_id = query.from_user.id

    #         # Assuming add_reminder method also takes current_user_task_id now
    #         self.db.add_reminder(user_id, task_id, reminder_time_minutes, current_user_task_id)
            
    #         # Send a new message for confirmation
    #         await update.effective_chat.send_message(
    #         text=f"Reminder set for Task ID: {task_id} — 30 minutes before the due time."
    #         )

    # async def handle_reminder_time_selection(self, update: Update, context: CallbackContext):
    #     query = update.callback_query
    #     await query.answer()

    #     data = query.data.split('_')
    #     task_id = context.user_data['selected_task_id_for_reminder']
    #     current_user_task_id = context.user_data['current_user_task_id_for_reminder']
    #     user_id = query.from_user.id

    #     if data[2] == 'custom':
    #         await query.edit_message_text(text="Enter custom reminder time in the format: 'X minutes/hours/days/weeks before'")
    #         context.user_data['awaiting_custom_reminder_input'] = True
    #     else:
    #         reminder_time_minutes = int(data[2])

    #         # Fetch the due date and due time from tasks table
    #         task_details = self.db.get_task_details_by_current_user_task_id(user_id, current_user_task_id)

    #         if task_details is None:
    #             await query.message.reply_text("Task details could not be fetched.")
    #             return

    #         due_date = task_details['due_date']
    #         due_time = task_details['due_time']

    #         # Fetch the updated_on time from reminders table if due_time is not set
    #         if due_time is None:
    #             reminder_record = self.db.get_reminder_updated_on(user_id, task_id)
    #             if reminder_record is None:
    #                 # Use current time if no reminder exists yet
    #                 updated_on = datetime.now()
    #             else:
    #                 updated_on = reminder_record['updated_on']
    #             due_time = updated_on.time()  # Use updated_on time as due_time if due_time is not set

    #         # If still no due time, set a default time (e.g., 23:59)
    #         if due_time is None:
    #             due_time = time(23, 59)

    #         # Combine due_date and due_time to form the complete due datetime
    #         due_datetime = datetime.combine(due_date, due_time)

    #         # Calculate reminder time
    #         reminder_time = due_datetime - timedelta(minutes=reminder_time_minutes)

    #         # Update the reminder in the database
    #         self.db.add_reminder(user_id, task_id, reminder_time, current_user_task_id)

    #         # Send confirmation message with the reminder time
    #         reminder_time_formatted = reminder_time.strftime('%Y-%m-%d %H:%M:%S')
    #         await query.message.delete()
    #         await context.bot.send_message(
    #             chat_id=user_id,
    #             text=f"Reminder set for task ID {task_id}, {reminder_time_minutes} minutes before the due time.\nThe reminder will be sent at: {reminder_time_formatted}"
    #         )

    async def handle_reminder_time_selection(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()

        data = query.data.split('_')
        task_id = context.user_data['selected_task_id_for_reminder']
        current_user_task_id = context.user_data['current_user_task_id_for_reminder']
        user_id = query.from_user.id

        if data[2] == 'custom':
            await query.edit_message_text(text="Enter custom reminder time in the format: 'X minutes/hours/days/weeks before'")
            context.user_data['awaiting_custom_reminder_input'] = True
        else:
            reminder_time_minutes = int(data[2])

            # Fetch the due date and due time from tasks table
            task_details = self.db.get_current_user_task_id_from_tasks(user_id, current_user_task_id)

            if task_details is None:
                await query.message.reply_text("Task details could not be fetched.")
                return

            due_date = task_details['due_date']
            due_time = task_details['due_time']

            # Convert timedelta to time if necessary
            if isinstance(due_time, timedelta):
                due_time = (datetime.min + due_time).time()

            # Fetch the updated_on time from reminders table if due_time is not set
            if due_time is None:
                reminder_record = self.db.get_reminder_updated_on(user_id, task_id)
                if reminder_record is None:
                    # Use current time if no reminder exists yet
                    updated_on = datetime.now()
                else:
                    updated_on = reminder_record['updated_on']
                due_time = updated_on.time()  # Use updated_on time as due_time if due_time is not set

            # If still no due time, set a default time (e.g., 23:59)
            if due_time is None:
                due_time = time(23, 59)

            # Combine due_date and due_time to form the complete due datetime
            due_datetime = datetime.combine(due_date, due_time)

            # Calculate reminder time
            reminder_datetime = due_datetime - timedelta(minutes=reminder_time_minutes)
            reminder_date = reminder_datetime.date()
            reminder_time = reminder_datetime.time()

            # Update the reminder in the database
            self.db.add_reminder(user_id, task_id, reminder_date, reminder_time, current_user_task_id)

            # Send confirmation message with the reminder time
            await context.bot.send_message(chat_id=user_id, text=f"Reminder set for task ID {task_id}, {reminder_time_minutes} minutes before the due time.\nThe reminder will be sent at: {reminder_datetime.strftime('%Y-%m-%d %H:%M:%S')}")

            # Remove the reminder selection buttons
            try:
                await query.message.delete()
            except Exception as e:
                print(f"Error deleting message: {e}")

    async def handle_message(self, update: Update, context: CallbackContext):
        if context.user_data.get('awaiting_custom_reminder_input'):
            custom_input = update.message.text.lower().strip()
            match = re.match(r'(\d+)\s*(minutes|hours|days|weeks)\s*before', custom_input)
            if not match:
                await update.message.reply_text("Invalid format. Please use the format: 'X minutes/hours/days/weeks before'")
                return

            quantity, unit = int(match[1]), match[2]
            multiplier = {'minutes': 1, 'hours': 60, 'days': 1440, 'weeks': 10080}
            reminder_time_minutes = quantity * multiplier[unit]

            task_id = context.user_data['selected_task_id_for_reminder']
            current_user_task_id = context.user_data['current_user_task_id_for_reminder']
            user_id = update.message.from_user.id

            self.db.add_reminder(user_id, task_id, reminder_time_minutes, current_user_task_id)
            await update.message.reply_text(f"Custom reminder set for task ID {task_id}, {custom_input} before the due time.")
            context.user_data['awaiting_custom_reminder_input'] = False
        else:
            # Handle other messages
            await update.message.reply_text(self.handle_response(update.message.text))

    async def check_and_send_reminders(self):
        now = datetime.now(pytz.timezone('Asia/Kuala_Lumpur'))
        reminders = self.db.get_due_reminders(now)

        print(f"Checking reminders at {now}. Found {len(reminders)} reminders.")

        for reminder in reminders:
            chat_id = reminder['user_id']
            task_id = reminder['task_id']
            reminder_date = reminder['reminder_date']
            reminder_time = reminder['reminder_time']

            print(f"Processing reminder for task ID {task_id} at {reminder_date} {reminder_time}")

            # Fetch task details to get the description
            task_details = self.db.get_task_details(chat_id, task_id)
            if not task_details:
                print(f"Task details not found for task ID {task_id}")
                continue  # If task details are not found, skip this reminder

            task_description = task_details['description']

            # Convert timedelta to time if necessary
            if isinstance(reminder_time, timedelta):
                total_seconds = reminder_time.total_seconds()
                hours = int(total_seconds // 3600)
                minutes = int((total_seconds % 3600) // 60)
                seconds = int(total_seconds % 60)
                reminder_time = time(hours, minutes, seconds)

            # Combine reminder_date and reminder_time to form the complete datetime
            reminder_datetime = datetime.combine(reminder_date, reminder_time)
            reminder_datetime = pytz.timezone('Asia/Kuala_Lumpur').localize(reminder_datetime)

            print(f"Reminder datetime: {reminder_datetime}, now: {now}")

            if reminder_datetime <= now:
                print(f"Sending reminder for task ID {task_id} to user {chat_id}")
                # Send the reminder message to the user
                await self.application.bot.send_message(chat_id, text=f"Reminder for task '{task_description}' (ID: {task_id}): This task is due soon!")

                # Mark the reminder as sent
                self.db.mark_reminder_as_sent(reminder['id'])
            else:
                print(f"Reminder datetime {reminder_datetime} is in the future, not sending yet.")

        # Sleep for a short duration to prevent overlapping instances
        await asyncio.sleep(1)

    # async def handle_message(self, update, context):
    #     if 'awaiting_time_input' in context.user_data and context.user_data['awaiting_time_input']:
    #         time_input = update.message.text
    #         try:
    #             # Example for absolute time
    #             reminder_time = datetime.strptime(time_input, "%H:%M %Y-%m-%d")
    #             task_id = context.user_data['selected_task_id_for_reminder']
    #             user_id = update.message.from_user.id
    #             if self.db.add_reminder(user_id, task_id, reminder_time):
    #                 await update.message.reply_text("Reminder set successfully for {reminder_time.strftime('%H:%M on %Y-%m-%d')}.")
    #             else:
    #                 await update.message.reply_text("Failed to set reminder. Please try again.")
    #             context.user_data['awaiting_time_input'] = False  # Reset the flag
    #         except ValueError:
    #             await update.message.reply_text("Invalid time format. Please use HH:MM YYYY-MM-DD format.")

    # def check_reminders(self):
    #     # This function will fetch upcoming reminders and schedule them
    #     reminders = self.db.get_upcoming_reminders()
    #     for reminder in reminders:
    #         self.schedule_reminder(reminder['user_id'], reminder['task_id'], reminder['reminder_time'])

    # def schedule_reminder(self, user_id, task_id, reminder_time):
    #     # Schedule a single reminder
    #     self.scheduler.add_job(
    #         self.send_reminder, 
    #         trigger=DateTrigger(run_date=reminder_time), 
    #         args=[user_id, task_id]
    #     )

    # async def send_reminder(self, user_id, task_id):
    #     task = self.db.get_task(user_id, task_id)
    #     if task:
    #         message = f"Reminder: Your task '{task['description']}' is due soon!"
    #         await self.application.bot.send_message(chat_id=user_id, text=message)
    #         self.db.mark_reminder_as_sent(task['id'])



    def handle_response(self, text: str) -> str:
        processed: str = text.lower()
        if 'hello' in processed:
            return 'Hey there!'
        if 'what are u' in processed:
            return 'I am ChatLah!'
        if 'how are u' in processed:
            return 'I am good!'
        return 'I do not understand what you wrote...'

    async def handle_message(self, update: Update, context: CallbackContext):
        message_type: str = update.message.chat.type
        text: str = update.message.text

        print(f'User ({update.message.chat.id}) in {message_type}: "{text}"')

        if message_type == 'group':
            if self.bot_username in text:
                new_text: str = text.replace(self.bot_username, '').strip()
                response: str = self.handle_response(new_text)
            else:
                return
        else:
            response: str = self.handle_response(text)

        print('Bot:', response)
        await update.message.reply_text(response)

    async def error(self, update: Update, context: CallbackContext):
        print(f'Update {update} caused error {context.error}')


    # async def run_reminder_checker(self):
    #     loop = asyncio.get_event_loop()
    #     loop.create_task(self.check_and_send_reminders())

    def shutdown(self, signum, frame):
        print("Shutting down...")
        if self.reminder_task:
            self.reminder_task.cancel()
        self.loop.stop()
        self.scheduler.shutdown(wait=False)
        sys.exit(0)

    def run(self):
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('create', self.create_task_command)],
            states={
                WAITING_FOR_DESCRIPTION: [MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_description)]
            },
            fallbacks=[],
        )

        self.application.add_handler(CommandHandler('start', self.start_command))
        self.application.add_handler(CommandHandler('help', self.help_command))
        self.application.add_handler(CommandHandler('custom', self.custom_command))
        self.application.add_handler(CommandHandler('create', self.create_task_command))
        self.application.add_handler(CommandHandler('list', self.list_tasks_command))
        self.application.add_handler(CommandHandler('delete', self.delete_task_command))
        # bot.application.add_handler(CallbackQueryHandler(bot.handle_task_deletion_confirmation, pattern='^(confirm_delete|cancel_delete)_'))
        self.application.add_handler(CommandHandler('status', self.status_task_command))
        self.application.add_handler(conv_handler)
        self.application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message))
        self.application.add_error_handler(self.error)

        # Due date and calendar handlers
        self.application.add_handler(CommandHandler('set_due_date', self.set_due_date_command))
        self.application.add_handler(CallbackQueryHandler(self.handle_year_selection, pattern='^year_\d+$'))
        self.application.add_handler(CallbackQueryHandler(self.handle_due_date_selection, pattern='^due_\d+$'))

        # Handle month selection by number
        self.application.add_handler(CallbackQueryHandler(self.handle_month_selection, pattern='^month_[A-Za-z]+$'))

        self.application.add_handler(CallbackQueryHandler(self.handle_day_selection, pattern='^day_\d+$'))
        # self.application.add_handler(CallbackQueryHandler(self.toggle_view, pattern='^toggle_details$'))

        # Specific month handlers for the calendar
        self.application.add_handler(CallbackQueryHandler(self.handle_early_half_year_selection, pattern='^next_months$'))
        self.application.add_handler(CallbackQueryHandler(self.handle_late_half_year_selection, pattern='^previous_months$'))

        # Task status update handlers
        self.application.add_handler(CallbackQueryHandler(self.choose_task_status, pattern='^status_'))
        self.application.add_handler(CallbackQueryHandler(self.bulk_update_status_command, pattern='^bulk_update_status$'))
        self.application.add_handler(CallbackQueryHandler(self.set_bulk_task_status, pattern='^bulk_set_'))
        self.application.add_handler(CallbackQueryHandler(self.set_task_status, pattern='^set_status_'))

        # Due time 
        self.application.add_handler(CommandHandler('set_due_time', self.set_due_time_command))
        self.application.add_handler(CallbackQueryHandler(self.handle_hour_selection, pattern='^hour_\\d{2}$'))
        self.application.add_handler(CallbackQueryHandler(self.handle_minute_selection, pattern='^minute_'))
        # self.application.add_handler(CallbackQueryHandler(self.handle_period_selection, pattern="^period_"))

        #search 
        self.application.add_handler(CommandHandler('search', self.search_tasks_command))
        self.application.add_handler(CommandHandler('search_full_details', self.search_full_task_details_command))

        # reminder
        self.application.add_handler(CommandHandler('reminder', self.set_reminder_command))
        self.application.add_handler(CallbackQueryHandler(self.handle_set_reminder, pattern='^set_reminder_'))
        self.application.add_handler(CallbackQueryHandler(self.handle_reminder_time_selection, pattern='^reminder_time_'))
        self.application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message))
        # Schedule the reminder checker to run every 30 seconds
        self.scheduler.add_job(self.check_and_send_reminders, IntervalTrigger(seconds=10), max_instances=1)
        # self.application.add_handler(CallbackQueryHandler(self.update_task_status, pattern='^update_status_'))
        # self.application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message))

        print('Polling...')
        self.application.run_polling()

if __name__ == '__main__':
    bot = TelegramBot(TOKEN, BOT_USERNAME)
    bot.run()



    