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
from database import Database
from html import escape
import textwrap
import time as tm
import logging

# # Setup basic logging
# logging.basicConfig(level=logging.DEBUG)
# logger = logging.getLogger(__name__)

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

    # async def list_tasks_command(self, update: Update, context: CallbackContext):
    #     user_id = update.message.from_user.id
    #     print(f"Listing tasks for user {user_id}")  # Debugging output
    #     tasks = self.db.list_tasks(user_id)
    #     print(f"Tasks for user {user_id}: {tasks}")  # Debugging output
    #     if not tasks:
    #         await update.message.reply_text("You have no tasks.")
    #         return

    #     task_list = "\n".join([f"{task[0]}. {task[1]} ({task[2]})" for task in tasks])
    #     buttons = [
    #         [InlineKeyboardButton(f"{task[0]}. {task[1]} ({task[2]})", callback_data=f"status_{task[0]}")]
    #         for task in tasks
    #     ]
    #     # Add a button for bulk update
    #     buttons.append([InlineKeyboardButton("Update All Tasks", callback_data="bulk_update_status")])
    #     await update.message.reply_text(
    #         f"Your tasks:\n{task_list}\n\nUse /delete [task_id] to delete a task, /status to update a task status, or select a task to set a due date /set_due_date [task_id].",
    #         reply_markup=InlineKeyboardMarkup(buttons)
    #     )

    # # # code modified for table line included (26/6/2024)
    # async def list_tasks_command(self, update: Update, context: CallbackContext):
    #     user_id = update.message.from_user.id
    #     tasks = self.db.list_tasks(user_id)
    #     if not tasks:
    #         await update.message.reply_text("You have no tasks.")
    #         return

    #     # Define column widths including the padding and separator spaces
    #     id_width = 3  # "ID" + space
    #     description_width = 20  # Max description width
    #     due_date_width = 10  # "YYYY-MM-DD"
    #     status_width = 10  # Status description

    #     # Build header with lines
    #     header = f"{'ID':<{id_width}} | {'Description':<{description_width}} | {'Due Date':<{due_date_width}} | {'Status':<{status_width}}"
    #     separator = f"{'-' * id_width}-+-{'-' * description_width}-+-{'-' * due_date_width}-+-{'-' * status_width}"

    #     lines = [header, separator]

    #     for task_id, description, status, due_date in tasks:
    #         due_date_display = due_date.strftime('%Y-%m-%d') if due_date else "Not Set"
    #         wrapped_description = textwrap.wrap(description, width=description_width)  # Wrap text to not exceed the column width
    #         first_line = True

    #         for line in wrapped_description:
    #             if first_line:
    #                 lines.append(f"{task_id:<{id_width}} | {line:<{description_width}} | {due_date_display:<{due_date_width}} | {status:<{status_width}}")
    #                 first_line = False
    #             else:
    #                 # For extra lines of a wrapped description, ensure alignment
    #                 lines.append(f"{' ':<{id_width}} | {line:<{description_width}} | {' ':<{due_date_width}} | {' ':<{status_width}}")
    #         lines.append(separator)  # Add a separator after each task

    #     task_list = "\n".join(lines)
    #     await update.message.reply_text(f"<pre>{task_list}</pre>", parse_mode='HTML')

    #     # Additional instructions message
    #     instruction_text = "Use /delete [task_id] to delete a task, /status to update a task status, " \
    #                     "or select a task to set a due date with /set_due_date [task_id]."
    #     await update.message.reply_text(instruction_text)

    # # new code added for more details and less details (default) - 27/6/2024

    # async def list_tasks_command(self, message_or_update, context: CallbackContext):
    #     # Determine if the input is an Update or Message object
    #     if isinstance(message_or_update, Update):
    #         message = message_or_update.message
    #     else:
    #         message = message_or_update  # It's already a Message object

    #     user_id = message.from_user.id  # This extracts user ID from the message

    #     # Fetch tasks from the database
    #     tasks = self.db.list_tasks(user_id)
    #     if not tasks:
    #         await message.reply_text("You have no tasks.")
    #         return
    #     # addded to verify 
    #     print(f"Retrieved tasks: {tasks}")

    #     detailed_view = context.user_data.get('detailed_view', False)
    #     mobile_view = context.user_data.get('mobile_view', False)  # Assuming you have a way to toggle or set this

    #     # Adjusted column widths based on device view
    #     id_width = 2 if not detailed_view else 5
    #     description_width = 29 if mobile_view else 30
    #     status_width = 15
    #     due_date_width = 10 if detailed_view else 0  # Due Date only in detailed view

    #     # Build headers
    #     header_elements = [
    #         f"{'ID':<{id_width}}",
    #         f"{'Description':<{description_width}}",
    #         f"{'Due Date':<{due_date_width}}" if detailed_view else "",
    #         f"{'Status':<{status_width}}"
    #     ]
    #     header = " | ".join(filter(None, header_elements))
    #     separator_elements = [
    #         '-' * id_width,
    #         '-' * description_width,
    #         '-' * due_date_width if detailed_view else "",
    #         '-' * status_width
    #     ]
    #     separator = "-+-".join(filter(None, separator_elements))

    #     lines = [header, separator]

    #     for task_id, description, status, due_date in tasks:
    #         wrapped_description = textwrap.wrap(description, width=description_width)
    #         first_line = True
    #         due_date_display = due_date.strftime('%Y-%m-%d') if due_date else "Not Set"

    #         for line in wrapped_description:
    #             line_elements = [
    #                 f"{task_id:<{id_width}}" if first_line else f"{' ':<{id_width}}",
    #                 f"{line:<{description_width}}",
    #                 f"{due_date_display:<{due_date_width}}" if detailed_view else "",
    #                 f"{status:<{status_width}}" if first_line else f"{' ':<{status_width}}"
    #             ]
    #             lines.append(" | ".join(filter(None, line_elements)))
    #             first_line = False

    #         lines.append(separator)

    #     task_list = "\n".join(lines)

    #     print(f"Final task list message: \n{task_list}")

    #     toggle_button_text = "More Details >>" if not detailed_view else "<< Less Details"
    #     toggle_button = InlineKeyboardButton(toggle_button_text, callback_data="toggle_details")
    #     reply_markup = InlineKeyboardMarkup([[toggle_button]])

    #     # Send the table with toggle button

    #     print(f"Final task list message: {task_list}")

    #     await message.reply_text(f"<pre>{task_list}</pre>", reply_markup=reply_markup, parse_mode='HTML')

    #     # Additional instructions message sent separately
    #     instruction_text = "Use /delete [task_id] to delete a task, /status to update a task status, or select a task to set a due date with /set_due_date [task_id]."
    #     await message.reply_text(instruction_text)

    # async def toggle_view(self, update: Update, context: CallbackContext):
    #     query = update.callback_query
    #     if query is None:
    #         print("Received an update without a callback query. This is unexpected in this context.")
    #         return

    #     await query.answer()  # Acknowledge the callback query.

    #     # Toggle the detailed view state.
    #     context.user_data['detailed_view'] = not context.user_data.get('detailed_view', False)
    #     # added for verify 
    #     print(f"Detailed view state is now: {context.user_data['detailed_view']}")

    #     # Ensure the message object is available
    #     if query.message:
    #         try:
    #             # Refresh the task list with the new view setting
    #             await self.list_tasks_command(query.message, context)
    #         except Exception as e:
    #             print(f"Error updating the task list view: {str(e)}")
    #     else:
    #         print("Callback query does not contain reference to the original message.")

    # the correct code before add in due time
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

    #     # Column width calculations
    #     max_id_width = max((len(str(task[0])) for task in tasks), default=2) + 1
    #     max_desc_width = 30  # Fixed width for the description column
    #     max_status_width = max((len(task[2]) for task in tasks), default=7)
    #     max_due_date_width = max((len(task[3].strftime('%Y-%m-%d')) if task[3] else 7 for task in tasks), default=10)

    #     headers = f"{'ID':<{max_id_width}} | {'Description':<{max_desc_width}} | {'Status':<{max_status_width}}"
    #     if detailed_view:
    #         headers += f" | {'Due Date':<{max_due_date_width}}"
    #     separators = f"{'-' * max_id_width}-+-{'-' * max_desc_width}-+-{'-' * max_status_width}"
    #     if detailed_view:
    #         separators += f"-+-{'-' * max_due_date_width}"

    #     lines = [headers, separators]

    #     for task_id, description, status, due_date in tasks:
    #         # Wrap long descriptions properly
    #         wrapped_description = textwrap.wrap(description, width=max_desc_width)
    #         for i, line in enumerate(wrapped_description):
    #             if i == 0:
    #                 # First line includes ID and other details
    #                 task_line = f"{task_id:<{max_id_width}} | {line:<{max_desc_width}} | {status:<{max_status_width}}"
    #                 if detailed_view:
    #                     due_date_display = due_date.strftime('%Y-%m-%d') if due_date else "Not Set"
    #                     task_line += f" | {due_date_display:<{max_due_date_width}}"
    #             else:
    #                 # Subsequent lines only include the wrapped part of the description
    #                 task_line = f"{'':<{max_id_width}} | {line:<{max_desc_width}} | {'':<{max_status_width}}"
    #                 if detailed_view:
    #                     task_line += f" | {'':<{max_due_date_width}}"
    #             lines.append(task_line)
    #         # Separator after the entire task entry
    #         lines.append(separators)

    #     task_list = "\n".join(lines)
    #     toggle_button_text = "Show More Details >>" if not detailed_view else "<< Show Less Details"
    #     toggle_button = InlineKeyboardButton(toggle_button_text, callback_data="toggle_details")
    #     reply_markup = InlineKeyboardMarkup([[toggle_button]])

    #     await message.reply_text(f"<pre>{task_list}</pre>", reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    #     # Additional instructions message sent separately
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

    #     # Column width calculations similar to list_tasks_command
    #     max_id_width = max((len(str(task[0])) for task in tasks), default=2) + 1
    #     max_desc_width = 30  # Fixed width for the description column
    #     max_status_width = max((len(task[2]) for task in tasks), default=7)
    #     max_due_date_width = max((len(task[3].strftime('%Y-%m-%d')) if task[3] else 7 for task in tasks), default=10)

    #     headers = f"{'ID':<{max_id_width}} | {'Description':<{max_desc_width}} | {'Status':<{max_status_width}}"
    #     if context.user_data['detailed_view']:
    #         headers += f" | {'Due Date':<{max_due_date_width}}"
    #     separators = f"{'-' * max_id_width}-+-{'-' * max_desc_width}-+-{'-' * max_status_width}"
    #     if context.user_data['detailed_view']:
    #         separators += f"-+-{'-' * max_due_date_width}"

    #     lines = [headers, separators]

    #     for task_id, description, status, due_date in tasks:
    #         wrapped_description = textwrap.wrap(description, width=max_desc_width)
    #         for i, line in enumerate(wrapped_description):
    #             if i == 0:
    #                 task_line = f"{task_id:<{max_id_width}} | {line:<{max_desc_width}} | {status:<{max_status_width}}"
    #                 if context.user_data['detailed_view']:
    #                     due_date_display = due_date.strftime('%Y-%m-%d') if due_date else "Not Set"
    #                     task_line += f" | {due_date_display:<{max_due_date_width}}"
    #             else:
    #                 task_line = f"{'':<{max_id_width}} | {line:<{max_desc_width}} | {'':<{max_status_width}}"
    #                 if context.user_data['detailed_view']:
    #                     task_line += f" | {'':<{max_due_date_width}}"
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

    # this code work without showing in table 6 july 2024
    # async def list_tasks_command(self, update: Update, context: CallbackContext):
    #     user_id = update.message.from_user.id
    #     logger.debug(f"Handling list command for user {user_id}")
    #     try:
    #         tasks = self.db.list_tasks(user_id)  # Example function to fetch tasks
    #         if not tasks:
    #             await update.message.reply_text("You have no tasks.")
    #             logger.info(f"No tasks found for user {user_id}")
    #             return

    #         task_list = "\n".join([f"{task[0]}. {task[1]} - Status: {task[2]}" for task in tasks])
    #         await update.message.reply_text(f"Your tasks:\n{task_list}")
    #         logger.debug(f"Sent task list to user {user_id}: {task_list}")
    #     except Exception as e:
    #         logger.error(f"Error handling list command for user {user_id}: {str(e)}")
    #         await update.message.reply_text("An error occurred while fetching your tasks.")

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
    #     max_desc_width = 30  # Max description width for uniformity

    #     headers = f"{'ID':<3} | {'Description':<{max_desc_width}} | {'Status':<10}"
    #     if detailed_view:
    #         headers += " | {'Due Date':<10} | {'Due Time':<5}"
    #     separators = '-' * len(headers)

    #     lines = [headers, separators]
    #     for task_id, description, status, due_date, due_time in tasks:
    #         due_date_display = due_date.strftime('%Y-%m-%d') if due_date else "No date"
    #         due_time_display = self.format_time_or_duration(due_time)
    #         wrapped_description = textwrap.wrap(description, width=max_desc_width)

    #         for i, line in enumerate(wrapped_description):
    #             if i == 0:
    #                 task_line = f"{task_id:<3} | {line:<{max_desc_width}} | {status:<10}"
    #                 if detailed_view:
    #                     task_line += f" | {due_date_display:<10} | {due_time_display:<5}"
    #             else:
    #                 # Ensure subsequent lines of wrapped text align correctly under the description
    #                 task_line = f"{' ':<3} | {line:<{max_desc_width}} | {' ':<10}"
    #                 if detailed_view:
    #                     task_line += " | {' ':<10} | {' ':<5}"
    #             lines.append(task_line)
    #         lines.append(separators)  # Add a separator after each task

    #     task_list = "\n".join(lines)
    #     toggle_button_text = "<< Show Less Details" if detailed_view else "Show More Details >>"
    #     toggle_button = InlineKeyboardButton(toggle_button_text, callback_data="toggle_details")
    #     reply_markup = InlineKeyboardMarkup([[toggle_button]])

    #     await message.reply_text(f"<pre>{task_list}</pre>", reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    #     instruction_text = "Use /delete [task_id] to delete a task, /status [task_id] to update a task status, or select a task to set a due date with /set_due_date [task_id]."
    #     await message.reply_text(instruction_text)

    # code added and modify 9 july 2024 until toggle view
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

        for task in tasks:
            task_id, description, status, due_date, due_time = task
            due_date_display = due_date.strftime('%Y-%m-%d') if due_date else "No Date"
            due_time_display = self.format_time_or_duration(due_time) if due_time else "No Time"
            
            # Wrap descriptions to fit within the specified width
            wrapped_description = textwrap.wrap(description, width=description_width)

            for i, desc_line in enumerate(wrapped_description):
                if i == 0:
                    line = f"{task_id:<{id_width}} | {desc_line:<{description_width}} | {status:<{status_width}}"
                    if detailed_view:
                        line += f" | {due_date_display:<{date_width}} | {due_time_display:<{time_width}}"
                else:
                    line = f"{'':<{id_width}} | {desc_line:<{description_width}} | {'':<{status_width}}"
                    if detailed_view:
                        line += f" | {'':<{date_width}} | {'':<{time_width}}"
                lines.append(line)
            
            lines.append(separators)  # Separate each entry

        task_list = "\n".join(lines)
        toggle_button_text = "Show More Details >>" if not detailed_view else "<< Show Less Details"
        toggle_button = InlineKeyboardButton(toggle_button_text, callback_data="toggle_details")
        reply_markup = InlineKeyboardMarkup([[toggle_button]])

        await message.reply_text(f"<pre>{task_list}</pre>", reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        instruction_text = "Use /delete [task_id] to delete a task, /status [task_id] to update a task status, or select a task to set a due date with /set_due_date [task_id]."
        await message.reply_text(instruction_text)

    async def toggle_view(self, update: Update, context: CallbackContext):
        query = update.callback_query
        if not query:
            print("No callback query found.")
            return

        await query.answer()  # Acknowledge the callback query to stop the loading spinner on the button

        # Toggle the detailed view state in the user context
        context.user_data['detailed_view'] = not context.user_data.get('detailed_view', False)
        tasks = self.db.list_tasks(query.from_user.id)

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

        for task in tasks:
            task_id, description, status, due_date, due_time = task
            due_date_display = due_date.strftime('%Y-%m-%d') if due_date else "No Date"
            due_time_display = self.format_time_or_duration(due_time) if due_time else "No Time"
            wrapped_description = textwrap.wrap(description, width=description_width)

            for i, desc_line in enumerate(wrapped_description):
                if i == 0:
                    line = f"{task_id:<{id_width}} | {desc_line:<{description_width}} | {status:<{status_width}}"
                    if context.user_data['detailed_view']:
                        line += f" | {due_date_display:<{date_width}} | {due_time_display:<{time_width}}"
                else:
                    line = f"{'':<{id_width}} | {desc_line:<{description_width}} | {'':<{status_width}}"
                    if context.user_data['detailed_view']:
                        line += f" | {'':<{date_width}} | {'':<{time_width}}"
                lines.append(line)
            
            lines.append(separators)  # Separate each entry

        task_list = "\n".join(lines)
        toggle_button_text = "<< Show Less Details" if context.user_data['detailed_view'] else "Show More Details >>"
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
            [InlineKeyboardButton(status, callback_data=f"set_{status.replace(' ', '_')}_{task_id}")]
            for status in statuses
        ]
        await query.edit_message_text(text="Choose task status:", reply_markup=InlineKeyboardMarkup(buttons))

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

        data = query.data.split('_')  # Expected format "set_{status}_{user_task_id}"
        if len(data) < 3:
            await query.message.reply_text("Invalid data format.")
            return

        # Reconstruct the status with spaces if needed
        status = '_'.join(data[1:-1]).replace('_', ' ')
        user_task_id = data[-1]
        user_id = query.from_user.id

        success = self.db.update_task_status(user_id, int(user_task_id), status)
        if success:
            await query.message.reply_text(f"Task {user_task_id} status updated to {status}.")
        else:
            await query.message.reply_text("Failed to update task status. Please try again.")

    async def delete_task_command(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        if len(context.args) == 0:
            await update.message.reply_text("Please provide a task ID to delete. Usage: /delete [task_id]")
            return
        try:
            task_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Invalid task ID. Please provide a numeric task ID.")
            return

        if self.db.delete_task(user_id, task_id):
            await update.message.reply_text(f"Task {task_id} deleted.")
        else:
            await update.message.reply_text(f"Failed to delete task {task_id}.")

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

    # new coded enhanced for due time in selection 5 july 2024
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