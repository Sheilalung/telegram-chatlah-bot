code have problem on database - 6 July 2024 

main.py

from typing import Final
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler, CallbackQueryHandler, ContextTypes
from telegram.error import TimedOut
# new added features scheduling 
from telegram_bot_calendar import DetailedTelegramCalendar, LSTEP
import calendar
from datetime import datetime, date, time, timedelta 
from database import Database
from html import escape
import textwrap
import time as tm
import logging

TOKEN: Final = '6729973842:AAH8XIUZ_fMl1WdAlkdGnD1zOlyyZmC0ZCI'
BOT_USERNAME: Final = '@chat_lah_bot'
MAX_RETRIES = 3  # Maximum number of retries
WAITING_FOR_DESCRIPTION = 1

class TelegramBot:
    def __init__(self, token, bot_username):
        self.token = token
        self.bot_username = bot_username
        self.db = self.connect_to_database()
        self.application = self.connect_to_telegram()
        self.last_callback_time = None
        self.application.add_handler(CallbackQueryHandler(self.toggle_view, pattern='^toggle_details$'))

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
            return Database(host="localhost", user="root", password="", database="telegram_bot_db")
        except ConnectionError as e:
            print(e)
            raise

    async def start_command(self, update: Update, context: CallbackContext):
        await update.message.reply_text('Hello! Thanks for choosing me as your buddy, and feel free to chat with me as I am ChatLah!')

    async def help_command(self, update: Update, context: CallbackContext):
        await update.message.reply_text('I am ChatLah! Please type anything so I can respond!')

    async def custom_command(self, update: Update, context: CallbackContext):
        await update.message.reply_text('This is custom command!')

    async def create_task_command(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        description = ' '.join(context.args) if context.args else None
        if not description:
            await update.message.reply_text("Please provide a task description.")
            return

        task_id = self.db.create_task(user_id, description)
        if task_id:
            print(f"Task {task_id} created successfully.")
            await update.message.reply_text(f"Task created: {description} (ID: {task_id})")
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
    
    # new added code 5 july 2024
    async def update_task_description_command(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        if len(context.args) < 2:
            await update.message.reply_text("Please provide a task ID and a new description. Usage: /update [task_id] [new_description]")
            return
        try:
            user_task_id = int(context.args[0])
            new_description = ' '.join(context.args[1:])
        except ValueError:
            await update.message.reply_text("Invalid task ID. Please provide a numeric task ID.")
            return

        if self.db.update_task_description(user_id, user_task_id, new_description):
            await update.message.reply_text(f"Task {user_task_id} updated.")
        else:
            await update.message.reply_text(f"Failed to update task {user_task_id}. It may be marked as deleted.")

    # async def list_tasks_command(self, message_or_update, context: CallbackContext):
    #     if isinstance(message_or_update, Update):
    #         message = message_or_update.message
    #     else:
    #         message = message_or_update

    #     user_id = message.from_user.id
    #     tasks = self.db.list_tasks(user_id)
    #     if not tasks:
    #         await message.reply_text("You have no tasks.")
    #         return

    #     detailed_view = context.user_data.get('detailed_view', False)

    #     # Calculate maximum widths for proper alignment in the display table
    #     max_desc_width = max((len(task[1]) for task in tasks), default=11)
    #     max_status_width = max((len(task[2]) for task in tasks), default=7)
    #     max_due_date_width = max((len(task[3].strftime('%Y-%m-%d')) if isinstance(task[3], date) else 8 for task in tasks), default=10)
    #     max_due_time_width = max(
    #         (len(task[4].strftime('%H:%M')) if isinstance(task[4], time) else len(str(task[4])) for task in tasks),
    #         default=5
    #     )

    #     headers = f"{'ID':<3} | {'Description':<{max_desc_width}} | {'Status':<{max_status_width}}"
    #     if detailed_view:
    #         headers += f" | {'Due Date':<{max_due_date_width}} | {'Due Time':<{max_due_time_width}}"
    #     separators = f"{'-'*3}-+-{'-'*max_desc_width}-+-{'-'*max_status_width}"
    #     if detailed_view:
    #         separators += f"-+-{'-'*max_due_date_width}-+-{'-'*max_due_time_width}"

    #     lines = [headers, separators]
    #     for index, (task_id, description, status, due_date, due_time) in enumerate(tasks, start=1):
    #         wrapped_description = textwrap.wrap(description, width=max_desc_width)
    #         for i, line in enumerate(wrapped_description):
    #             due_date_display = due_date.strftime('%Y-%m-%d') if isinstance(due_date, date) else "Not Set"
    #             if isinstance(due_time, timedelta):
    #                 # Assuming due_time is stored as minutes in timedelta
    #                 hours = due_time.seconds // 3600
    #                 minutes = (due_time.seconds // 60) % 60
    #                 due_time_display = f'{hours:02}:{minutes:02}'
    #             elif isinstance(due_time, time):
    #                 due_time_display = due_time.strftime('%H:%M')
    #             else:
    #                 due_time_display = "Not Set"
    #             task_line = f"{index:<3} | {line:<{max_desc_width}} | {status:<{max_status_width}}"
    #             if detailed_view:
    #                 task_line += f" | {due_date_display:<{max_due_date_width}} | {due_time_display:<{max_due_time_width}}"
    #             lines.append(task_line)
    #         lines.append(separators)

    #     task_list = "\n".join(lines)
    #     toggle_button_text = "Show More Details >>" if not detailed_view else "<< Show Less Details"
    #     toggle_button = InlineKeyboardButton(toggle_button_text, callback_data="toggle_details")
    #     reply_markup = InlineKeyboardMarkup([[toggle_button]])

    #     await message.reply_text(f"<pre>{task_list}</pre>", reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    #     instruction_text = "Use /delete [task_id] to delete a task, /status to update a task status, or select a task to set a due date with /set_due_date [task_id]."
    #     await message.reply_text(instruction_text)

    # async def toggle_view(self, update: Update, context: CallbackContext):
    #     query = update.callback_query
    #     if not query:
    #         print("No callback query found.")
    #         return

    #     await query.answer()  # Acknowledge the callback query

    #     # Toggle the detailed view state in the user context
    #     context.user_data['detailed_view'] = not context.user_data.get('detailed_view', False)
    #     print(f"Toggled detailed view to: {context.user_data['detailed_view']}")

    #     user_id = query.from_user.id
    #     tasks = self.db.list_tasks(user_id)
    #     if not tasks:
    #         await query.edit_message_text(text="You have no tasks.")
    #         return

    #     max_id_width = max((len(str(task[0])) for task in tasks), default=2) + 1
    #     max_desc_width = max((len(task[1]) for task in tasks), default=11)
    #     max_status_width = max((len(task[2]) for task in tasks), default=7)
    #     max_due_date_width = max((len(task[3].strftime('%Y-%m-%d')) if isinstance(task[3], date) else 8 for task in tasks), default=10)
    #     max_due_time_width = max(
    #         (len(task[4].strftime('%H:%M')) if isinstance(task[4], time) else len(str(task[4])) for task in tasks),
    #         default=5
    #     )

    #     headers = f"{'ID':<{max_id_width}} | {'Description':<{max_desc_width}} | {'Status':<{max_status_width}}"
    #     if context.user_data['detailed_view']:
    #         headers += f" | {'Due Date':<{max_due_date_width}} | {'Due Time':<{max_due_time_width}}"
    #     separators = f"{'-' * max_id_width}-+-{'-' * max_desc_width}-+-{'-' * max_status_width}"
    #     if context.user_data['detailed_view']:
    #         separators += f"-+-{'-' * max_due_date_width}-+-{'-' * max_due_time_width}"

    #     lines = [headers, separators]

    #     for task_id, description, status, due_date, due_time in tasks:
    #         wrapped_description = textwrap.wrap(description, width=max_desc_width)
    #         for i, line in enumerate(wrapped_description):
    #             if i == 0:
    #                 due_date_display = due_date.strftime('%Y-%m-%d') if isinstance(due_date, date) else "Not Set"
    #                 if isinstance(due_time, timedelta):
    #                     hours = due_time.seconds // 3600
    #                     minutes = (due_time.seconds // 60) % 60
    #                     due_time_display = f'{hours:02}:{minutes:02}'
    #                 elif isinstance(due_time, time):
    #                     due_time_display = due_time.strftime('%H:%M')
    #                 else:
    #                     due_time_display = "Not Set"
    #                 task_line = f"{task_id:<{max_id_width}} | {line:<{max_desc_width}} | {status:<{max_status_width}}"
    #                 if context.user_data['detailed_view']:
    #                     task_line += f" | {due_date_display:<{max_due_date_width}} | {due_time_display:<{max_due_time_width}}"
    #             else:
    #                 task_line = f"{'':<{max_id_width}} | {line:<{max_desc_width}} | {'':<{max_status_width}}"
    #                 if context.user_data['detailed_view']:
    #                     task_line += f" | {'':<{max_due_date_width}} | {'':<{max_due_time_width}}"
    #             lines.append(task_line)
    #         lines.append(separators)  # Add a separator after each task entry

    #     task_list = "\n".join(lines)
    #     toggle_button_text = "Show More Details >>" if not context.user_data['detailed_view'] else "<< Show Less Details"
    #     toggle_button = InlineKeyboardButton(toggle_button_text, callback_data="toggle_details")
    #     reply_markup = InlineKeyboardMarkup([[toggle_button]])

    #     # Use edit_message_text to update the existing message
    #     if query.message:
    #         try:
    #             await query.edit_message_text(text=f"<pre>{task_list}</pre>", reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    #         except Exception as e:
    #             print(f"Error while updating task list: {str(e)}")
    #     else:
    #         print("No message found in query to update.")

    async def list_tasks_command(self, message_or_update, context: CallbackContext):
        if isinstance(message_or_update, Update):
            message = message_or_update.message
        else:
            message = message_or_update

        user_id = message.from_user.id
        tasks = self.db.list_tasks(user_id)
        if not tasks:
            await message.reply_text("You have no tasks.")
            return

        detailed_view = context.user_data.get('detailed_view', False)

        # Initialize widths outside the loop to ensure they are always defined.
        max_desc_width = max((len(task['description']) for task in tasks), default=11)
        max_status_width = max((len(task['status']) for task in tasks), default=7)
        max_due_date_width = max((len(task['due_date'].strftime('%Y-%m-%d')) if task['due_date'] else 8 for task in tasks), default=10)
        max_due_time_width = max((len(task['due_time'].strftime('%H:%M')) if task['due_time'] else 5 for task in tasks), default=5)

        headers = f"{'ID':<3} | {'Description':<{max_desc_width}} | {'Status':<{max_status_width}}"
        if detailed_view:
            headers += f" | {'Due Date':<{max_due_date_width}} | {'Due Time':<{max_due_time_width}}"
        separators = f"{'-'*3}-+-{'-'*max_desc_width}-+-{'-'*max_status_width}"
        if detailed_view:
            separators += f"-+-{'-'*max_due_date_width}-+-{'-'*max_due_time_width}"

        lines = [headers, separators]
        display_id = 1
        for task in tasks:
            if task['task_state'] != 'Deleted':
                task['display_id'] = display_id
                wrapped_description = textwrap.wrap(task['description'], width=max_desc_width)
                for i, line in enumerate(wrapped_description):
                    due_date_display = task['due_date'].strftime('%Y-%m-%d') if task['due_date'] else "Not Set"
                    due_time_display = task['due_time'].strftime('%H:%M') if task['due_time'] else "Not Set"
                    task_line = f"{display_id:<3} | {line:<{max_desc_width}} | {task['status']:<{max_status_width}}"
                    if detailed_view:
                        task_line += f" | {due_date_display:<{max_due_date_width}} | {due_time_display:<{max_due_time_width}}"
                    if i == 0:
                        lines.append(task_line)
                    else:
                        lines.append(f"{'':<3} | {line:<{max_desc_width}} | {'':<{max_status_width}}")
                    lines.append(separators)
                display_id += 1  # Increment display_id for each active task

        task_list = "\n".join(lines)
        toggle_button_text = "Show More Details >>" if not detailed_view else "<< Show Less Details"
        toggle_button = InlineKeyboardButton(toggle_button_text, callback_data="toggle_details")
        reply_markup = InlineKeyboardMarkup([[toggle_button]])

        await message.reply_text(f"<pre>{task_list}</pre>", reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        instruction_text = "Use /delete [task_id] to delete a task, /status [task_id] to update a task status, or select a task to set a due date with /set_due_date [task_id]."
        await message.reply_text(instruction_text)

    def format_task_list(self, tasks, detailed_view):
        # Initial setup for table headers and maximum widths
        max_desc_width = max((len(task['description']) for task in tasks), default=20)
        max_status_width = max((len(task['status']) for task in tasks), default=10)
        max_due_date_width = max((len(task['due_date'].strftime('%Y-%m-%d')) if task['due_date'] else 8 for task in tasks), default=10)
        max_due_time_width = max((len(task['due_time'].strftime('%H:%M')) if task['due_time'] else 5 for task in tasks), default=5)

        headers = f"{'ID':<3} | {'Description':<{max_desc_width}} | {'Status':<{max_status_width}}"
        if detailed_view:
            headers += f" | {'Due Date':<{max_due_date_width}} | {'Due Time':<{max_due_time_width}}"
        separators = f"{'-'*3}-+-{'-'*max_desc_width}-+-{'-'*max_status_width}"
        if detailed_view:
            separators += f"-+-{'-'*max_due_date_width}-+-{'-'*max_due_time_width}"

        lines = [headers, separators]
        for index, task in enumerate(tasks, start=1):
            description = textwrap.wrap(task['description'], width=max_desc_width)
            first_line = True
            for line in description:
                due_date_display = task['due_date'].strftime('%Y-%m-%d') if task['due_date'] else "Not Set"
                due_time_display = task['due_time'].strftime('%H:%M') if task['due_time'] else "Not Set"
                task_line = f"{index:<3} | {line:<{max_desc_width}} | {task['status']:<{max_status_width}}"
                if detailed_view:
                    if first_line:
                        task_line += f" | {due_date_display:<{max_due_date_width}} | {due_time_display:<{max_due_time_width}}"
                        first_line = False
                    else:
                        task_line += f" | {'':<{max_due_date_width}} | {'':<{max_due_time_width}}"
                lines.append(task_line)
                lines.append(separators)

        return "\n".join(lines)
    
    async def toggle_view(self, update: Update, context: CallbackContext):
        query = update.callback_query
        if not query:
            print("No callback query found.")
            return

        await query.answer()  # Acknowledge the callback query

        # Toggle the detailed view state in the user context
        context.user_data['detailed_view'] = not context.user_data.get('detailed_view', False)
        print(f"Toggled detailed view to: {context.user_data['detailed_view']}")

        user_id = query.from_user.id
        tasks = self.db.list_tasks(user_id)  # Ensure this fetches tasks with 'task_state'
        active_tasks = [task for task in tasks if task['task_state'] != 'Deleted']

        if not active_tasks:
            await query.edit_message_text(text="You have no tasks.")
            return

        # Use the same task list formatting method
        task_list = self.format_task_list(active_tasks, context.user_data['detailed_view'])

        # Update the message with the new task list
        toggle_button_text = "Show More Details >>" if not context.user_data['detailed_view'] else "<< Show Less Details"
        toggle_button = InlineKeyboardButton(toggle_button_text, callback_data="toggle_details")
        reply_markup = InlineKeyboardMarkup([[toggle_button]])

        try:
            await query.edit_message_text(text=f"<pre>{task_list}</pre>", reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        except Exception as e:
            print(f"Error while updating task list: {str(e)}")
            
    # async def choose_task_status(self, update: Update, context: CallbackContext):
    #     query = update.callback_query
    #     await query.answer()

    #     task_id = int(query.data.split('_')[1])
    #     context.user_data['task_id'] = task_id

    #     statuses = ["Incomplete", "In Progress", "Complete", "Deferred", "Cancelled"]
    #     buttons = [
    #         [InlineKeyboardButton(status, callback_data=f"set_{status.replace(' ', '_')}_{task_id}")]
    #         for status in statuses
    #     ]
    #     await query.edit_message_text(text="Choose task status:", reply_markup=InlineKeyboardMarkup(buttons))

    async def choose_task_status(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()

        task_id = int(query.data.split('_')[1])  # Assume callback data format is "status_{task_id}"
        user_id = query.from_user.id
        task = self.db.get_task_by_id(user_id, task_id)  # Fetching task using primary key ID

        if task:
            print(f"Debug: User selected task ID {task_id}, task: {task}")  # Debug statement
            statuses = ["Incomplete", "In Progress", "Complete", "Deferred", "Cancelled"]
            buttons = [
                [InlineKeyboardButton(status, callback_data=f"set_{status.replace(' ', '_')}_{task_id}")]
                for status in statuses
            ]
            await query.edit_message_text(text=f"Choose task status for: {task['description']}", reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await query.edit_message_text("Task not found.")

    async def bulk_update_status_command(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()

        status_options = ["Incomplete", "In Progress", "Complete", "Deferred", "Cancelled"]
        buttons = [
            [InlineKeyboardButton(status, callback_data=f"bulk_set_{status.replace(' ', '_').lower()}")]
            for status in status_options
        ]
        await query.edit_message_text("Select a status to apply to all tasks:", reply_markup=InlineKeyboardMarkup(buttons))

    async def set_bulk_task_status(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()

        data = query.data.split('_')  # Expected format "bulk_set_{status}"
        if len(data) < 3:
            await query.message.reply_text("Invalid data format.")
            return

        # Converting back to correct status format by replacing underscores with spaces
        status = '_'.join(data[2:]).replace('_', ' ')

        user_id = query.from_user.id

        success = self.db.update_all_tasks_status(user_id, status)
        if success:
            await query.message.reply_text(f"All tasks updated to {status}.")
        else:
            await query.message.reply_text("Failed to update all tasks. Please try again.")

    # async def set_task_status(self, update: Update, context: CallbackContext):
    #     query = update.callback_query
    #     await query.answer()

    #     data = query.data.split('_')  # Expected format "set_{status}_{user_task_id}"
    #     if len(data) < 3:
    #         await query.message.reply_text("Invalid data format.")
    #         return

    #     # Reconstruct the status with spaces if needed
    #     status = '_'.join(data[1:-1]).replace('_', ' ')
    #     user_task_id = data[-1]
    #     user_id = query.from_user.id

    #     success = self.db.update_task_status(user_id, int(user_task_id), status)
    #     if success:
    #         await query.message.reply_text(f"Task {user_task_id} status updated to {status}.")
    #     else:
    #         await query.message.reply_text("Failed to update task status. Please try again.")

    async def set_task_status(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()

        data = query.data.split('_')  # Expected format "set_{status}_{display_id}"
        if len(data) < 3:
            await query.message.reply_text("Invalid data format.")
            return

        status = '_'.join(data[1:-1]).replace('_', ' ')
        display_id = int(data[-1])
        user_id = query.from_user.id

        tasks = self.db.list_tasks(user_id)
        selected_task = next((task for task in tasks if task['display_id'] == display_id), None)

        if selected_task:
            user_task_id = selected_task['user_task_id']
            success = self.db.update_task_status(user_id, user_task_id, status)
            if success:
                # Use display_id in the feedback message to the user
                await query.message.reply_text(f"Task {display_id} status updated to {status}.")
            else:
                await query.message.reply_text("Failed to update task status. Please try again.")
        else:
            await query.message.reply_text("Task not found.")

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
            user_task_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Invalid task ID. Please provide a numeric task ID.")
            return

        if self.db.delete_task(user_id, user_task_id):
            await update.message.reply_text(f"Task {user_task_id} deleted.")
        else:
            await update.message.reply_text(f"Failed to delete task {user_task_id}.")

    # async def status_task_command(self, update: Update, context: CallbackContext):
    #     user_id = update.message.from_user.id
    #     print(f"Listing tasks for user {user_id} for status update")  # Debugging output
    #     tasks = self.db.list_tasks(user_id)
    #     print(f"Tasks for user {user_id}: {tasks}")  # Debugging output
    #     if not tasks:
    #         await update.message.reply_text("You have no tasks.")
    #         return

    #     buttons = [
    #         [InlineKeyboardButton(f"{task[0]}. {task[1]} ({task[2]})", callback_data=f"status_{task[0]}")]
    #         for task in tasks
    #     ]

    #     buttons.append([InlineKeyboardButton("Bulk Update All Tasks", callback_data="bulk_update_status")])

    #     await update.message.reply_text("Select a task to update its status or choose to bulk update all tasks:", reply_markup=InlineKeyboardMarkup(buttons))

    async def status_task_command(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        tasks = self.db.list_tasks(user_id)
        if not tasks:
            await update.message.reply_text("You have no tasks.")
            return

        buttons = [
            [InlineKeyboardButton(f"{task['display_id']}. {task['description']} ({task['status']})", callback_data=f"status_{task['user_task_id']}")]
            for task in tasks
        ]

        buttons.append([InlineKeyboardButton("Bulk Update All Tasks", callback_data="bulk_update_status")])

        await update.message.reply_text("Select a task to update its status or choose to bulk update all tasks:", reply_markup=InlineKeyboardMarkup(buttons))

    async def set_due_date_command(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        if len(context.args) == 0:
            await update.message.reply_text("Please provide a task ID. Usage: /set_due_date [task_id]")
            return
        task_id = context.args[0]
        context.user_data['task_id_for_due_date'] = task_id

        # Trigger the selection of a year when /set_due_date is called
        buttons = [[InlineKeyboardButton(str(year), callback_data=f"year_{year}")] for year in range(datetime.now().year, datetime.now().year + 5)]
        await update.message.reply_text("Please choose a year:", reply_markup=InlineKeyboardMarkup(buttons))

    async def handle_due_date_selection(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        user_task_id = int(query.data.split('_')[1])  # Extract task ID from callback data
        context.user_data['user_task_id_for_due_date'] = user_task_id  # Save user_task_id for later use

        # Get the internal task ID
        task_id = self.db.get_internal_task_id(user_id, user_task_id)
        if task_id is None:
            await query.message.reply_text(text="Task not found.")
            return

        context.user_data['task_id_for_due_date'] = task_id  # Save the internal task ID for later use
        print(f"Using internal task ID {task_id} for due date setting")  # Debugging output

        # Call or write a function to display the calendar here
        await self.prompt_calendar_for_due_date(update, context)

    async def handle_year_selection(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()
        selected_year = int(query.data.split('_')[1])
        context.user_data['selected_year'] = selected_year
        # Prompt for the first half of the year
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
            user_id = update.effective_user.id  # Assuming you are storing the user_id in context when initiating the task selection

            # Retrieve user_task_id stored previously in user data
            user_task_id = context.user_data.get('task_id_for_due_date')

            # Call the method to set due date in database
            if user_task_id and self.db.set_task_due_date(user_id, user_task_id, formatted_date):
                await query.message.reply_text(f"Due date set to {formatted_date} for task ID {user_task_id}.")
            else:
                await query.message.reply_text("Failed to set due date. Please try again.")
        else:
            await query.message.reply_text("Invalid day selection.")

    async def prompt_calendar_for_due_date(self, update: Update, context: CallbackContext):
        buttons = [[InlineKeyboardButton(str(year), callback_data=f"year_{year}")] for year in range(datetime.now().year, datetime.now().year + 5)]
        await update.message.reply_text("Please choose a year:", reply_markup=InlineKeyboardMarkup(buttons))

    # new coded enhanced for due time in selection 5/7/2024
    async def set_due_time_command(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        if len(context.args) == 0:
            await update.message.reply_text("Please provide a task ID. Usage: /set_due_time [task_id]")
            return
        task_id = context.args[0]
        context.user_data['task_id_for_due_time'] = task_id

        # Organize hours into two rows: 1-6 and 7-12
        buttons = [
            [InlineKeyboardButton(f"{i:02d}", callback_data=f"hour_{i:02d}") for i in range(1, 7)],
            [InlineKeyboardButton(f"{i:02d}", callback_data=f"hour_{i:02d}") for i in range(7, 13)]
        ]
        print("Hour buttons structure:", buttons)
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
        print("Minute buttons structure:", keyboard_layout)
        await query.edit_message_text(text="Please choose minutes:", reply_markup=InlineKeyboardMarkup(keyboard_layout))

    async def handle_minute_selection(self, update: Update, context: CallbackContext):
        query = update.callback_query
        if query:
            await query.answer()

        minute = int(query.data.split('_')[1])
        hour = context.user_data['selected_hour']
        time_str = f"{hour:02d}:{minute:02d}"
        task_id = context.user_data['task_id_for_due_time']
        
        # Update the task due time in the database
        if self.db.set_task_due_time(update.effective_user.id, task_id, time_str):
            # Send a new message instead of editing the current one
            await query.message.reply_text(f"Due time set to {time_str} for task ID {task_id}.")
        else:
            await query.message.reply_text("Failed to set due time. Please try again.")

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
        self.application.add_handler(CallbackQueryHandler(self.set_task_status, pattern='^set_'))

        # Due time 
        self.application.add_handler(CommandHandler('set_due_time', self.set_due_time_command))
        self.application.add_handler(CallbackQueryHandler(self.handle_hour_selection, pattern='^hour_\\d{2}$'))
        self.application.add_handler(CallbackQueryHandler(self.handle_minute_selection, pattern='^minute_'))


        print('Polling...')
        self.application.run_polling()

if __name__ == '__main__':
    bot = TelegramBot(TOKEN, BOT_USERNAME)
    bot.run()


database.py 

import mysql.connector
from mysql.connector import Error

class Database:
    def __init__(self, host="localhost", user="root", password="", database="telegram_bot_db"):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.connection = None
        self.connect_to_db()

    def connect_to_db(self):
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database
            )
            print("Database connection successful")
        except Error as err:
            print(f"Error connecting to database: {err}")
            raise ConnectionError("Failed to connect to database")

    def verify_connection(self):
        try:
            if self.connection is None or not self.connection.is_connected():
                self.connect_to_db()
        except Error as err:
            print(f"Error verifying connection: {err}")
            raise

    def close(self):
        try:
            if self.connection and self.connection.is_connected():
                self.connection.close()
                print("Database connection closed")
        except Error as err:
            print(f"Error closing the database connection: {err}")

    def get_next_user_task_id(self, user_id):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            sql = "SELECT COALESCE(MAX(user_task_id), 0) + 1 FROM tasks WHERE user_id = %s"
            cursor.execute(sql, (user_id,))
            next_id = cursor.fetchone()[0]
            print(f"Calculated next user_task_id: {next_id} for user_id: {user_id}")
            return next_id
        finally:
            cursor.close()

    # def create_task(self, user_id, description):
    #     user_task_id = self.get_next_user_task_id(user_id)
    #     self.verify_connection()
    #     cursor = self.connection.cursor()
    #     try:
    #         sql = "INSERT INTO tasks (user_id, user_task_id, description, status) VALUES (%s, %s, %s, 'incomplete')"
    #         cursor.execute(sql, (user_id, user_task_id, description))
    #         self.connection.commit()
    #         print(f"Task created successfully with user_task_id: {user_task_id} for User ID: {user_id}")
    #         return user_task_id
    #     except Error as err:
    #         print(f"Error creating task: {err}")
    #         return None
    #     finally:
    #         cursor.close()

    def create_task(self, user_id, description):
        user_task_id = self.get_next_user_task_id(user_id)
        display_id = self.get_next_display_id(user_id)
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            sql = "INSERT INTO tasks (user_id, user_task_id, display_id, description, status) VALUES (%s, %s, %s, %s, 'incomplete')"
            cursor.execute(sql, (user_id, user_task_id, display_id, description))
            self.connection.commit()
            print(f"Task created successfully with display_id: {display_id} for User ID: {user_id}")
            return user_task_id
        except Error as err:
            print(f"Error creating task: {err}")
            return None
        finally:
            cursor.close()

    # new added code 5 july 2024
    def update_task_description(self, user_id, user_task_id, new_description):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            sql = """
            UPDATE tasks
            SET description = %s, task_state = 'Modified'
            WHERE user_id = %s AND user_task_id = %s AND task_state != 'Deleted'
            """
            cursor.execute(sql, (new_description, user_id, user_task_id))
            self.connection.commit()
            print(f"Task description updated and marked as modified for user_task_id: {user_task_id}.")
            return cursor.rowcount > 0
        finally:
            cursor.close()

    # def list_tasks(self, user_id):
    #     self.verify_connection()
    #     cursor = self.connection.cursor()
    #     try:
    #         sql = "SELECT description, status, due_date, due_time FROM tasks WHERE user_id = %s ORDER BY id"
    #         cursor.execute(sql, (user_id,))
    #         tasks = cursor.fetchall()
    #         return [(index + 1, *task) for index, task in enumerate(tasks)]  # Remap IDs for user display
    #     finally:
    #         cursor.close()

    def list_tasks(self, user_id):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            sql = """
            SELECT id, user_task_id, display_id, description, status, due_date, due_time, task_state
            FROM tasks
            WHERE user_id = %s AND task_state != 'Deleted'
            ORDER BY display_id
            """
            cursor.execute(sql, (user_id,))
            tasks = cursor.fetchall()
            field_names = [i[0] for i in cursor.description]
            return [dict(zip(field_names, task)) for task in tasks]
        finally:
            cursor.close()

    def get_task_by_id(self, user_id, task_id):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            sql = "SELECT * FROM tasks WHERE user_id = %s AND id = %s AND task_state != 'Deleted'"
            cursor.execute(sql, (user_id, task_id))
            result = cursor.fetchone()
            return dict(zip([desc[0] for desc in cursor.description], result)) if result else None
        finally:
            cursor.close()

    # def update_task_status(self, user_id, user_task_id, status):
    #     self.verify_connection()
    #     cursor = self.connection.cursor()
    #     try:
    #         sql = "UPDATE tasks SET status = %s WHERE user_id = %s AND user_task_id = %s"
    #         cursor.execute(sql, (status, user_id, user_task_id))
    #         self.connection.commit()
    #         print(f"Rows affected: {cursor.rowcount}")  # Debugging output
    #         return cursor.rowcount > 0
    #     except mysql.connector.Error as err:
    #         print(f"Error updating task status: {err}")
    #         return False
    #     finally:
    #         cursor.close()

    def update_task_status(self, user_id, user_task_id, status):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            sql = """
            UPDATE tasks
            SET status = %s, task_state = 'Modified'
            WHERE user_id = %s AND user_task_id = %s AND task_state != 'Deleted'
            """
            cursor.execute(sql, (status, user_id, user_task_id))
            self.connection.commit()
            print(f"Rows affected: {cursor.rowcount}")  # Debugging output
            return cursor.rowcount > 0
        except mysql.connector.Error as err:
            print(f"Error updating task status: {err}")
            return False
        finally:
            cursor.close()

    def update_all_tasks_status(self, user_id, status):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            sql = "UPDATE tasks SET status = %s WHERE user_id = %s"
            cursor.execute(sql, (status, user_id))
            self.connection.commit()
            return cursor.rowcount > 0
        except mysql.connector.Error as err:
            print(f"Error updating task status: {err}")
            return False
        finally:
            cursor.close()

    # def delete_task(self, user_id, user_task_id):
    #     self.verify_connection()
    #     cursor = self.connection.cursor()
    #     try:
    #         # Delete the task
    #         sql = "DELETE FROM tasks WHERE user_id = %s AND user_task_id = %s"
    #         cursor.execute(sql, (user_id, user_task_id))
    #         rows_deleted = cursor.rowcount
    #         self.connection.commit()

    #         if rows_deleted:
    #             # Optionally, you might want to reassign user_task_ids here or just leave them as is
    #             print(f"Task {user_task_id} deleted successfully.")
    #         return rows_deleted > 0
    #     finally:
    #         cursor.close()

    def delete_task(self, user_id, user_task_id):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            # Mark the task as deleted
            sql = "UPDATE tasks SET task_state = 'Deleted' WHERE user_id = %s AND user_task_id = %s"
            cursor.execute(sql, (user_id, user_task_id))

            # Reassign display_ids
            sql_update = """
            UPDATE tasks
            SET display_id = display_id - 1
            WHERE user_id = %s AND display_id > (
                SELECT display_id FROM tasks WHERE user_id = %s AND user_task_id = %s
            ) AND task_state != 'Deleted'
            """
            cursor.execute(sql_update, (user_id, user_id, user_task_id))
            
            self.connection.commit()
            return True
        finally:
            cursor.close()

    # def set_task_due_date(self, user_id, user_task_id, due_date):
    #     self.verify_connection()
    #     cursor = self.connection.cursor()
    #     try:
    #         # Ensure you pass both user_id and user_task_id to uniquely identify the task
    #         sql = "UPDATE tasks SET due_date = %s WHERE user_id = %s AND user_task_id = %s"
    #         cursor.execute(sql, (due_date, user_id, user_task_id))
    #         self.connection.commit()
    #         print(f"Rows affected: {cursor.rowcount}")
    #         return cursor.rowcount > 0
    #     except mysql.connector.Error as err:
    #         print(f"Error setting task due date: {err}")
    #         return False
    #     finally:
    #         cursor.close()

    def set_task_due_date(self, user_id, user_task_id, due_date):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            sql = """
            UPDATE tasks SET due_date = %s
            WHERE user_id = %s AND user_task_id = %s AND task_state != 'Deleted'
            """
            cursor.execute(sql, (due_date, user_id, user_task_id))
            if cursor.rowcount > 0:
                self.connection.commit()
                print(f"Due date set successfully for task {user_task_id}.")
                return True
            else:
                print(f"No active task found for ID {user_task_id}.")
                return False
        except mysql.connector.Error as err:
            print(f"Error setting task due date: {err}")
            return False
        finally:
            cursor.close()

    # def update_task_due_date(self, task_id, due_date):
    #     try:
    #         with self.connection.cursor() as cursor:
    #             sql = "UPDATE tasks SET due_date = %s WHERE id = %s"
    #             cursor.execute(sql, (due_date, task_id))
    #         self.connection.commit()
    #         return True
    #     except Exception as e:
    #         print(f"Failed to update due date: {e}")
    #         return False
    #     finally:
    #         cursor.close()

    def update_task_status(self, user_id, user_task_id, status):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            sql = """
            UPDATE tasks
            SET status = %s, task_state = 'Modified'
            WHERE user_id = %s AND user_task_id = %s AND task_state != 'Deleted'
            """
            cursor.execute(sql, (status, user_id, user_task_id))
            self.connection.commit()
            return cursor.rowcount > 0
        except mysql.connector.Error as err:
            print(f"Error updating task status: {err}")
            return False
        finally:
            cursor.close()

    def set_task_due_time(self, user_id, task_id, due_time):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            sql = "UPDATE tasks SET due_time = %s WHERE user_id = %s AND user_task_id = %s"
            cursor.execute(sql, (due_time, user_id, task_id))
            self.connection.commit()
            return cursor.rowcount > 0
        finally:
            cursor.close()

    # def get_next_display_id(self):
    #     self.verify_connection()
    #     cursor = self.connection.cursor()
    #     try:
    #         sql = "SELECT MAX(display_id) FROM tasks WHERE task_state != 'Deleted'"
    #         cursor.execute(sql)
    #         max_id = cursor.fetchone()[0]
    #         return max_id + 1 if max_id else 1
    #     finally:
    #         cursor.close()

    def get_next_display_id(self, user_id):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            sql = "SELECT COALESCE(MAX(display_id), 0) + 1 FROM tasks WHERE user_id = %s AND task_state != 'Deleted'"
            cursor.execute(sql, (user_id,))
            next_id = cursor.fetchone()[0]
            return next_id
        finally:
            cursor.close()

    def get_internal_task_id(self, user_id, user_task_id):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            sql = "SELECT id FROM tasks WHERE user_id = %s AND user_task_id = %s"
            cursor.execute(sql, (user_id, user_task_id))
            result = cursor.fetchone()
            if result:
                print(f"Internal task ID for user_id {user_id} and user_task_id {user_task_id} is {result[0]}")
                return result[0]
            else:
                print(f"No task found for user_id {user_id} and user_task_id {user_task_id}")
                return None
        finally:
            cursor.close()

    def get_user_task_id_by_display_id(self, user_id, display_id):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            sql = """
            SELECT user_task_id 
            FROM tasks 
            WHERE user_id = %s AND display_id = %s AND task_state != 'Deleted'
            """
            cursor.execute(sql, (user_id, display_id))
            result = cursor.fetchone()
            if result:
                print(f"Debug: Mapping display_id {display_id} to user_task_id {result[0]}")  # Debug statement
                return result[0]
            else:
                print(f"Debug: No task found for user_id {user_id} and display_id {display_id}")  # Debug statement
                return None
        finally:
            cursor.close()


