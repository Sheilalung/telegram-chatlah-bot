from typing import Final
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler, CallbackQueryHandler, ContextTypes
from telegram.error import TimedOut
from telegram_bot_calendar import DetailedTelegramCalendar, LSTEP
import calendar
from datetime import datetime, timedelta, time
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

WAITING_FOR_TASK_TITLE = 1
WAITING_FOR_DESCRIPTION = 2
WAITING_FOR_ACTUAL_DESCRIPTION = 3
WAITING_FOR_SEARCH_TERM = 4
WAITING_FOR_TASK_ID_TO_DELETE = 5
WAITING_FOR_TASK_ID_TO_EDIT = 6
WAITING_FOR_NEW_TASK_TITLE = 7
WAITING_FOR_NEW_DESCRIPTION = 8

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
        user_id = update.message.from_user.id
        user_name = update.message.from_user.username

        self.db.save_user(user_id, user_name)
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

    async def help_command(self, update: Update, context: CallbackContext):
        help_text = """
    Hello! I'm ChatLah, your task management assistant. Here are some commands you can use:

    - /start: Start interacting with me.
    - /help: Display this help message.
    - /create [description]: Create a new task with description.
    - /edit [task_id]: Edit the title and description of a task.
    - /list: List all your current tasks.
    - /delete [task_id]: Delete a specific task.
    - /status [task_id]: Update the status of a specific task.
    - /set_due_date [task_id]: Set the due date for a specific task.
    - /set_due_time [task_id]: Set the due time for a specific task.
    - /search [keywords]: Search tasks by keywords.
    - /search_full_details: Show the full details for the task. 
    - /remind [task_id]: Set a reminder for a specific task.
    """
        await update.message.reply_text(help_text)

    async def custom_command(self, update: Update, context: CallbackContext):
        await update.message.reply_text('This is custom command!')

    async def create_task_command(self, update: Update, context: CallbackContext):
        await update.message.reply_text("Please provide a task title:")
        return WAITING_FOR_TASK_TITLE

    async def handle_task_title(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        task_title = update.message.text
        context.user_data['task_title'] = task_title
        await update.message.reply_text("Do you want to provide a description for the task? If yes, please type the description. If no, type 'No'.")
        return WAITING_FOR_DESCRIPTION

    async def handle_description(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        task_title = context.user_data.get('task_title')
        description = update.message.text

        if description.lower() == 'no':
            task_id = self.db.create_task(user_id, task_title, None)
            if task_id:
                await update.message.reply_text(f"Task '{task_title}' created successfully.")
            else:
                await update.message.reply_text("Failed to create task. Please try again.")
            return ConversationHandler.END

        elif description.lower() == 'yes':
            await update.message.reply_text("Please provide the description for the task:")
            return WAITING_FOR_ACTUAL_DESCRIPTION
        
    async def handle_actual_description(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        task_title = context.user_data.get('task_title')
        description = update.message.text

        task_id = self.db.create_task(user_id, task_title, description)
        if task_id:
            await update.message.reply_text(f"Task '{task_title}' created successfully with description '{description}'.")
        else:
            await update.message.reply_text("Failed to create task. Please try again.")
        return ConversationHandler.END
    
    async def edit_task_command(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        tasks = self.db.list_tasks(user_id)
        if not tasks:
            await update.message.reply_text("You have no tasks to edit.")
            return ConversationHandler.END

        buttons = [
            [InlineKeyboardButton(f"{task[0]}. {task[1]}", callback_data=f"edit_{task[0]}")]
            for task in tasks
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await update.message.reply_text("Select a task to edit:", reply_markup=reply_markup)
        return WAITING_FOR_TASK_ID_TO_EDIT

    async def handle_task_selection_to_edit(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        task_id = int(query.data.split('_')[1])  # Extract the task ID from the callback data
        task_details = self.db.get_task_details(user_id, task_id)
        
        if not task_details:
            await query.message.reply_text(text="Task details could not be fetched.")
            return ConversationHandler.END

        context.user_data['selected_task_id_to_edit'] = task_id
        context.user_data['original_description'] = task_details['description']
        try:
            await query.message.delete()  # Delete the previous message
        except Exception as e:
            print(f"Error deleting message: {e}")
        await query.message.reply_text(text="Please enter the new task title:")
        return WAITING_FOR_NEW_TASK_TITLE

    async def handle_new_task_title(self, update: Update, context: CallbackContext):
        new_task_title = update.message.text
        context.user_data['new_task_title'] = new_task_title
        buttons = [
            [InlineKeyboardButton("Yes", callback_data="edit_yes")],
            [InlineKeyboardButton("No", callback_data="edit_no")]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await update.message.reply_text("Do you want to update the task description?", reply_markup=reply_markup)
        return WAITING_FOR_NEW_DESCRIPTION

    async def handle_description_choice(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()
        choice = query.data.split('_')[1]
        
        if choice == "yes":
            try:
                await query.message.delete()  # Delete the previous message
            except Exception as e:
                print(f"Error deleting message: {e}")
            await query.message.reply_text(text="Please enter the new task description:")
            return WAITING_FOR_ACTUAL_DESCRIPTION
        else:
            user_id = query.from_user.id
            task_id = context.user_data['selected_task_id_to_edit']
            new_task_title = context.user_data['new_task_title']
            original_description = context.user_data['original_description']

            success = self.db.update_task(user_id, task_id, new_task_title, original_description)
            if success:
                await query.message.reply_text(f"Task {task_id} updated successfully.")
            else:
                await query.message.reply_text("Failed to update task. Please try again.")
            return ConversationHandler.END

    async def handle_new_task_description(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        task_id = context.user_data['selected_task_id_to_edit']
        new_task_title = context.user_data['new_task_title']
        new_description = update.message.text

        success = self.db.update_task(user_id, task_id, new_task_title, new_description)
        if success:
            await update.message.reply_text(f"Task {task_id} updated successfully.")
        else:
            await update.message.reply_text("Failed to update task. Please try again.")
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
        title_width = 20  # Adjust the width as needed
        status_width = 12
        date_width = 10
        time_width = 8

        headers = f"{'ID':<{id_width}} | {'Title':<{title_width}} | {'Status':<{status_width}}"
        if detailed_view:
            headers += f" | {'Due Date':<{date_width}} | {'Due Time':<{time_width}}"
        separators = '-' * len(headers)

        lines = [headers, separators]

        task_map = {}
        for idx, task in enumerate(tasks, 1):
            task_id, task_title, description, status, due_date, due_time = task
            due_date_display = due_date.strftime('%Y-%m-%d') if due_date else "No Date"
            due_time_display = self.format_time_or_duration(due_time) if due_time else "No Time"

            wrapped_title = textwrap.wrap(task_title, width=title_width)

            for i, title_line in enumerate(wrapped_title):
                if i == 0:
                    line = f"{idx:<{id_width}} | {title_line:<{title_width}} | {status:<{status_width}}"
                    if detailed_view:
                        line += f" | {due_date_display:<{date_width}} | {due_time_display:<{time_width}}"
                else:
                    line = f"{'':<{id_width}} | {title_line:<{title_width}} | {'':<{status_width}}"
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
        title_width = 15  # Adjust the width as needed
        date_width = 10
        time_width = 8

        if context.user_data['detailed_view']:
            headers = f"{'ID':<{id_width}} | {'Title':<{title_width}} | {'Due Date':<{date_width}} | {'Due Time':<{time_width}}"
        else:
            status_width = 12
            headers = f"{'ID':<{id_width}} | {'Title':<{title_width}} | {'Status':<{status_width}}"

        separators = '-' * len(headers)

        lines = [headers, separators]

        task_map = {}
        for idx, task in enumerate(tasks, 1):
            task_id, task_title, description, status, due_date, due_time = task
            due_date_display = due_date.strftime('%Y-%m-%d') if due_date else "No Date"
            due_time_display = self.format_time_or_duration(due_time) if due_time else "No Time"

            wrapped_title = textwrap.wrap(task_title, width=title_width)

            for i, title_line in enumerate(wrapped_title):
                if i == 0:
                    if context.user_data['detailed_view']:
                        line = f"{idx:<{id_width}} | {title_line:<{title_width}} | {due_date_display:<{date_width}} | {due_time_display:<{time_width}}"
                    else:
                        line = f"{idx:<{id_width}} | {title_line:<{title_width}} | {status:<{status_width}}"
                else:
                    if context.user_data['detailed_view']:
                        line = f"{'':<{id_width}} | {title_line:<{title_width}} | {'':<{date_width}} | {'':<{time_width}}"
                    else:
                        line = f"{'':<{id_width}} | {title_line:<{title_width}} | {'':<{status_width}}"
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

        data = query.data.split('_')  
        status = ' '.join(data[2:])  

        user_id = update.effective_user.id
        success = self.db.update_all_tasks_status(user_id, status)
        if success:
            await query.message.reply_text(f"All tasks updated to {status}.")
        else:
            await query.message.reply_text("Failed to update all tasks. Please try again.")

    async def set_task_status(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()

        data = query.data.split('_')  
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

    async def delete_task_command(self, update: Update, context: CallbackContext):
        await update.message.reply_text("Please provide a task ID to delete:")
        return WAITING_FOR_TASK_ID_TO_DELETE
    
    async def handle_task_id_to_delete(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        try:
            current_user_task_id = int(update.message.text)
        except ValueError:
            await update.message.reply_text("Invalid task ID. Please provide a numeric task ID.")
            return WAITING_FOR_TASK_ID_TO_DELETE

        if self.db.delete_task(user_id, current_user_task_id):
            await update.message.reply_text(f"Task {current_user_task_id} deleted.")
        else:
            await update.message.reply_text(f"Failed to delete task {current_user_task_id}.")
        return ConversationHandler.END

    async def status_task_command(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        tasks = self.db.list_tasks(user_id)
        if not tasks:
            await update.message.reply_text("You have no tasks.")
            return

        buttons = [
            [InlineKeyboardButton(f"{task[0]}. {task[1]} ({task[3]})", callback_data=f"status_{task[0]}")]
            for task in tasks
        ]
        # Add a button for bulk update
        buttons.append([InlineKeyboardButton("Bulk Update All Tasks", callback_data="bulk_update_status")])

        await update.message.reply_text(
            "Select a task to update its status or choose to bulk update all tasks:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

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

    async def handle_year_selection(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()
        selected_year = int(query.data.split('_')[1])
        context.user_data['selected_year'] = selected_year
        await self.handle_early_half_year_selection(update, context)

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

    async def prompt_calendar_for_due_date(self, update: Update, context: CallbackContext):
        buttons = [[InlineKeyboardButton(str(year), callback_data=f"year_{year}")] for year in range(datetime.now().year, datetime.now().year + 5)]
        await update.message.reply_text("Please choose a year:", reply_markup=InlineKeyboardMarkup(buttons))

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

        buttons = [
            [InlineKeyboardButton(f"{i:02d}", callback_data=f"hour_{i:02d}") for i in range(0, 6)],
            [InlineKeyboardButton(f"{i:02d}", callback_data=f"hour_{i:02d}") for i in range(6, 12)],
            [InlineKeyboardButton(f"{i:02d}", callback_data=f"hour_{i:02d}") for i in range(12, 18)],
            [InlineKeyboardButton(f"{i:02d}", callback_data=f"hour_{i:02d}") for i in range(18, 24)]
        ]
        await update.message.reply_text("Please choose an hour:", reply_markup=InlineKeyboardMarkup(buttons))

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

    async def search_full_task_details_command(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        tasks = self.db.search_tasks_full_details(user_id)
        if not tasks:
            await update.message.reply_text("No tasks with a due date set.")
            return

        response_text = "Tasks with a due date:\n\n" + "\n".join(
            f"{task['current_user_task_id']}. {task['task_title']} (Status: {task['status']}, Due Date: {task['due_date'].strftime('%Y-%m-%d')})"
            for task in tasks
        )
        await update.message.reply_text(response_text)

    async def search_tasks_command(self, update: Update, context: CallbackContext):
        await update.message.reply_text("Please provide a search term:")
        return WAITING_FOR_SEARCH_TERM

    # Add a new handler method for search term input
    async def handle_search_term(self, update: Update, context: CallbackContext):
        search_term = update.message.text.lower()
        user_id = update.message.from_user.id
        matching_tasks = self.db.search_tasks(user_id, search_term)  # Use the updated method

        if not matching_tasks:
            await update.message.reply_text("No tasks found matching your criteria.")
            return ConversationHandler.END

        response_text = "Here are the tasks matching your search:\n\n" + "\n".join(
            f"{task['current_user_task_id']}. {task['task_title']} (Description: {task['description']}, Status: {task['status']})"
            for task in matching_tasks
        )
        await update.message.reply_text(response_text)
        return ConversationHandler.END

    async def set_reminder_command(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        tasks = self.db.list_tasks_for_reminders(user_id)
        if not tasks:
            await update.message.reply_text("You have no tasks with due dates set to set reminders for.")
            return
        
        buttons = [
            [InlineKeyboardButton(f"{task['current_user_task_id']}. {task['task_title']}", callback_data=f"set_reminder_{task['current_user_task_id']}")]
            for task in tasks
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        await update.message.reply_text("Select a task to set a reminder:", reply_markup=reply_markup)

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
            [InlineKeyboardButton("1 day before", callback_data="reminder_time_1440_minutes")]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)

        await query.message.reply_text(
            text=f"Task {task_id} due date is: {due_date} and due time is: {due_time_str}\nPlease select a reminder time:",
            reply_markup=reply_markup
        )

        # Remove the reminder selection buttons
        await query.message.delete()

    async def handle_reminder_time_selection(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()

        data = query.data.split('_')
        task_id = context.user_data['selected_task_id_for_reminder']
        current_user_task_id = context.user_data['current_user_task_id_for_reminder']
        user_id = query.from_user.id

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

            # Fetch task details to get the title
            task_details = self.db.get_task_details(chat_id, task_id)
            if not task_details:
                print(f"Task details not found for task ID {task_id}")
                continue  # If task details are not found, skip this reminder

            task_title = task_details['task_title']

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
                await self.application.bot.send_message(chat_id, text=f"Reminder for task '{task_title}' (ID: {task_id}): This task is due soon!")

                # Mark the reminder as sent
                self.db.mark_reminder_as_sent(reminder['id'])
            else:
                print(f"Reminder datetime {reminder_datetime} is in the future, not sending yet.")

        # Sleep for a short duration to prevent overlapping instances
        await asyncio.sleep(1)

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

    def shutdown(self, signum, frame):
        print("Shutting down...")
        if self.reminder_task:
            self.reminder_task.cancel()
        self.loop.stop()
        self.scheduler.shutdown(wait=False)
        sys.exit(0)

    def run(self):
        create_conv_handler = ConversationHandler(
            entry_points=[CommandHandler('create', self.create_task_command)],
            states={
                WAITING_FOR_TASK_TITLE: [MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_task_title)],
                WAITING_FOR_DESCRIPTION: [MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_description)],
                WAITING_FOR_ACTUAL_DESCRIPTION: [MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_actual_description)]
            },
            fallbacks=[]
        )

        search_conv_handler = ConversationHandler(
            entry_points=[CommandHandler('search', self.search_tasks_command)],
            states={
                WAITING_FOR_SEARCH_TERM: [MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_search_term)]
            },
            fallbacks=[]
        )

        delete_conv_handler = ConversationHandler(
            entry_points=[CommandHandler('delete', self.delete_task_command)],
            states={
                WAITING_FOR_TASK_ID_TO_DELETE: [MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_task_id_to_delete)]
            },
            fallbacks=[]
        )

        edit_task_conv_handler = ConversationHandler(
            entry_points=[CommandHandler('edit', self.edit_task_command)],
            states={
                WAITING_FOR_TASK_ID_TO_EDIT: [CallbackQueryHandler(self.handle_task_selection_to_edit, pattern='^edit_')],
                WAITING_FOR_NEW_TASK_TITLE: [MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_new_task_title)],
                WAITING_FOR_NEW_DESCRIPTION: [CallbackQueryHandler(self.handle_description_choice, pattern='^edit_')],
                WAITING_FOR_ACTUAL_DESCRIPTION: [MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_new_task_description)],
            },
            fallbacks=[]
        )

        self.application.add_handler(CommandHandler('start', self.start_command))
        self.application.add_handler(CommandHandler('help', self.help_command))
        self.application.add_handler(CommandHandler('custom', self.custom_command))
        self.application.add_handler(CommandHandler('list', self.list_tasks_command))
        self.application.add_handler(CommandHandler('status', self.status_task_command))
        self.application.add_handler(create_conv_handler)
        self.application.add_handler(search_conv_handler)
        self.application.add_handler(delete_conv_handler)
        self.application.add_handler(edit_task_conv_handler)
        self.application.add_handler(CommandHandler('edit', self.edit_task_command))
        self.application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message))
        self.application.add_error_handler(self.error)

        # Due date and calendar handlers
        self.application.add_handler(CommandHandler('set_due_date', self.set_due_date_command))
        self.application.add_handler(CallbackQueryHandler(self.handle_year_selection, pattern='^year_\d+$'))
        self.application.add_handler(CallbackQueryHandler(self.handle_due_date_selection, pattern='^due_\d+$'))
        self.application.add_handler(CallbackQueryHandler(self.handle_month_selection, pattern='^month_[A-Za-z]+$'))
        self.application.add_handler(CallbackQueryHandler(self.handle_day_selection, pattern='^day_\d+$'))
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

        #search 
        # self.application.add_handler(CommandHandler('search', self.search_tasks_command))
        self.application.add_handler(CommandHandler('search_full_details', self.search_full_task_details_command))

        # reminder
        self.application.add_handler(CommandHandler('reminder', self.set_reminder_command))
        self.application.add_handler(CallbackQueryHandler(self.handle_set_reminder, pattern='^set_reminder_'))
        self.application.add_handler(CallbackQueryHandler(self.handle_reminder_time_selection, pattern='^reminder_time_'))
        self.application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message))
        self.scheduler.add_job(self.check_and_send_reminders, IntervalTrigger(seconds=10), max_instances=1)

        print('Polling...')
        self.application.run_polling()

if __name__ == '__main__':
    bot = TelegramBot(TOKEN, BOT_USERNAME)
    bot.run()
