    def run(self):
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('create', self.create_task_command)],
            states={
                # WAITING_FOR_DESCRIPTION: [MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_description)]
                WAITING_FOR_TASK_TITLE: [MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_task_title)],
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
        self.application.add_handler(CommandHandler('search', self.search_tasks_command))
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