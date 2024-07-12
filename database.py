import mysql.connector
from mysql.connector import Error

class Database:
    # def __init__(self, host="localhost", user="root", password="", database="telegram_bot_db"):
    def __init__(self, host="mychatlahbotserver.mysql.database.azure.com", user="sheila@mychatlahbotserver", password="JoelLim1212!", database="telegram_bot_db"):
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

    # Define states
    REMINDER_TIME_STATE = 1

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

    def create_task(self, user_id, description):
        user_task_id = self.get_next_user_task_id(user_id)
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            sql = "INSERT INTO tasks (user_id, user_task_id, current_user_task_id, description, status) VALUES (%s, %s, %s, %s, 'incomplete')"
            cursor.execute(sql, (user_id, user_task_id, user_task_id, description))
            self.connection.commit()
            return user_task_id
        finally:
            cursor.close()

    def list_tasks(self, user_id):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            sql = "SELECT id, user_task_id, description, status, due_date, due_time FROM tasks WHERE user_id = %s AND is_deleted = 0 ORDER BY user_task_id"
            cursor.execute(sql, (user_id,))
            tasks = cursor.fetchall()

            # Update current_user_task_id to maintain correct order after deletions
            for index, task in enumerate(tasks):
                current_task_id = index + 1
                sql_update = "UPDATE tasks SET current_user_task_id = %s WHERE id = %s"
                cursor.execute(sql_update, (current_task_id, task[0]))
            
            self.connection.commit()

            # Fetch updated tasks with current_user_task_id
            sql = "SELECT current_user_task_id, description, status, due_date, due_time FROM tasks WHERE user_id = %s AND is_deleted = 0 ORDER BY current_user_task_id"
            cursor.execute(sql, (user_id,))
            tasks = cursor.fetchall()
            return tasks
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

    def update_task_status(self, user_id, current_user_task_id, status):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            # Check the current status of the task
            cursor.execute("SELECT status FROM tasks WHERE user_id = %s AND current_user_task_id = %s AND is_deleted = 0", (user_id, current_user_task_id))
            result = cursor.fetchone()
            if result is None:
                print(f"No active task found with current_user_task_id {current_user_task_id}")
                return False

            current_status = result[0]
            print(f"Current status of task {current_user_task_id} is {current_status}")

            # If the current status is already the desired status, acknowledge and return success
            if current_status == status:
                print(f"Task {current_user_task_id} is already in the status '{status}'")
                return True

            # Update the status if it is different from the current status
            sql = "UPDATE tasks SET status = %s WHERE user_id = %s AND current_user_task_id = %s AND is_deleted = 0"
            cursor.execute(sql, (status, user_id, current_user_task_id))
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
            # Update status for all active tasks of a specific user
            sql = """
            UPDATE tasks 
            SET status = %s 
            WHERE user_id = %s AND is_deleted = 0
            """
            cursor.execute(sql, (status, user_id))
            self.connection.commit()
            if cursor.rowcount > 0:
                print(f"All tasks for user {user_id} updated to {status}.")
                return True
            else:
                print("No tasks updated. Check if tasks exist or if they are all deleted.")
                return False
        except mysql.connector.Error as err:
            print(f"Error updating task statuses: {err}")
            return False
        finally:
            cursor.close()

    # def delete_task(self, user_id, user_task_id):
    #     self.verify_connection()
    #     cursor = self.connection.cursor()
    #     try:
    #         # Mark the task as deleted
    #         sql = "UPDATE tasks SET is_deleted = TRUE WHERE user_id = %s AND user_task_id = %s"
    #         cursor.execute(sql, (user_id, user_task_id))
    #         self.connection.commit()

    #         # Reorder remaining tasks to update current_user_task_id
    #         sql = "SELECT id FROM tasks WHERE user_id = %s AND is_deleted = 0 ORDER BY user_task_id"
    #         cursor.execute(sql, (user_id,))
    #         remaining_tasks = cursor.fetchall()

    #         for index, task in enumerate(remaining_tasks):
    #             current_task_id = index + 1
    #             sql_update = "UPDATE tasks SET current_user_task_id = %s WHERE id = %s"
    #             cursor.execute(sql_update, (current_task_id, task[0]))
            
    #         self.connection.commit()
    #         return cursor.rowcount > 0
    #     finally:
    #         cursor.close()

    # # code the true for current user task id 9 july 2024
    # def delete_task(self, user_id, user_task_id):
    #     self.verify_connection()
    #     cursor = self.connection.cursor()
    #     try:
    #         self.connection.start_transaction()

    #         # Mark the task as deleted and reset the current_user_task_id
    #         sql = """
    #         UPDATE tasks 
    #         SET is_deleted = 1, current_user_task_id = NULL
    #         WHERE user_id = %s AND user_task_id = %s;
    #         """
    #         cursor.execute(sql, (user_id, user_task_id))

    #         # Check if the task was successfully marked as deleted
    #         if cursor.rowcount == 0:
    #             print("No task was marked as deleted; check user_task_id and user_id.")
    #             self.connection.rollback()
    #             return False

    #         # Re-index current_user_task_id for the remaining tasks
    #         cursor.execute("SET @rownum := 0;")
    #         sql = """
    #         UPDATE tasks 
    #         SET current_user_task_id = (@rownum := @rownum + 1)
    #         WHERE user_id = %s AND is_deleted = 0
    #         ORDER BY user_task_id;
    #         """
    #         cursor.execute(sql, (user_id,))

    #         self.connection.commit()
    #         return True
    #     except mysql.connector.Error as err:
    #         print(f"Error while deleting/updating task: {err}")
    #         self.connection.rollback()
    #         return False
    #     finally:
    #         cursor.close()

    def delete_task(self, user_id, current_user_task_id):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            # Check if a transaction is already open; if not, start a new one
            if not self.connection.in_transaction:
                self.connection.start_transaction()

            # Fetch the internal database ID using current_user_task_id to ensure correct task operation
            cursor.execute("SELECT id FROM tasks WHERE user_id = %s AND current_user_task_id = %s AND is_deleted = 0", (user_id, current_user_task_id))
            task = cursor.fetchone()

            if not task:
                print("No active task found with this ID.")
                self.connection.rollback()  # Ensure to rollback if no task is found
                return False

            # Mark the task as deleted
            cursor.execute("UPDATE tasks SET is_deleted = 1, current_user_task_id = NULL WHERE id = %s", (task[0],))

            if cursor.rowcount == 0:
                print("Failed to mark the task as deleted.")
                self.connection.rollback()
                return False

            # Re-index current_user_task_id for the remaining tasks
            cursor.execute("SET @rownum := 0;")
            cursor.execute("""
            UPDATE tasks 
            SET current_user_task_id = (@rownum := @rownum + 1)
            WHERE user_id = %s AND is_deleted = 0
            ORDER BY user_task_id;
            """, (user_id,))

            self.connection.commit()
            return True
        except mysql.connector.Error as err:
            print(f"Error while deleting/updating task: {err}")
            self.connection.rollback()
            return False
        finally:
            cursor.close()

    # code can't use for doble confirm delete task
    # def delete_task(self, user_id, user_task_id):
    #     self.verify_connection()
    #     cursor = self.connection.cursor()
    #     try:
    #         self.connection.start_transaction()
    #         cursor.execute("SELECT is_deleted FROM tasks WHERE user_id = %s AND user_task_id = %s", (user_id, user_task_id))
    #         task = cursor.fetchone()
    #         if not task:
    #             print("Task does not exist.")
    #             self.connection.rollback()
    #             return False
    #         if task[0] == 1:
    #             print("Task already marked as deleted.")
    #             self.connection.rollback()
    #             return False

    #         cursor.execute("""
    #             UPDATE tasks SET is_deleted = 1, current_user_task_id = NULL
    #             WHERE user_id = %s AND user_task_id = %s
    #         """, (user_id, user_task_id))
    #         if cursor.rowcount == 0:
    #             print("No task was marked as deleted; check user_task_id and user_id.")
    #             self.connection.rollback()
    #             return False
            
    #         cursor.execute("SET @rownum := 0;")
    #         cursor.execute("""
    #             UPDATE tasks SET current_user_task_id = (@rownum := @rownum + 1)
    #             WHERE user_id = %s AND is_deleted = 0 ORDER BY user_task_id
    #         """, (user_id,))
    #         self.connection.commit()
    #         return True
    #     except mysql.connector.Error as err:
    #         print(f"Error while deleting/updating task: {err}")
    #         self.connection.rollback()
    #         return False
    #     finally:
    #         cursor.close()

    def set_task_due_date(self, user_id, current_user_task_id, due_date):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            # Fetch the current due date for comparison
            cursor.execute(
                "SELECT due_date FROM tasks WHERE user_id = %s AND current_user_task_id = %s AND is_deleted = 0",
                (user_id, current_user_task_id)
            )
            result = cursor.fetchone()
            if result is None:
                return False, "No active task found with the given ID."

            current_due_date = result[0]
            print(f"Current due date: {current_due_date}")

            # Check if the new due date is the same as the current due date
            if current_due_date == due_date:
                print(f"The due date is already set to {due_date}.")
                return True, "The due date is already set to this value."

            # Update due date only if it is different
            sql = "UPDATE tasks SET due_date = %s WHERE user_id = %s AND current_user_task_id = %s AND is_deleted = 0"
            cursor.execute(sql, (due_date, user_id, current_user_task_id))
            self.connection.commit()
            affected_rows = cursor.rowcount
            print(f"Rows affected: {affected_rows}")
            return affected_rows > 0, ""
        except mysql.connector.Error as err:
            print(f"Error setting task due date: {err}")
            return False, f"Error setting task due date: {err}"
        finally:
            cursor.close()

    def get_task_due_date(self, user_id, current_user_task_id):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                "SELECT due_date FROM tasks WHERE user_id = %s AND current_user_task_id = %s",
                (user_id, current_user_task_id)
            )
            result = cursor.fetchone()
            if result:
                return result[0]
            return None
        finally:
            cursor.close()

    # Update set_task_due_time to use current_user_task_id
    def set_task_due_time(self, user_id, current_user_task_id, due_time):
        self.verify_connection()
        cursor = self.connection.cursor(buffered=True)
        try:
            # Check if the task is active and fetch the current due time
            cursor.execute(
                "SELECT due_time FROM tasks WHERE user_id = %s AND current_user_task_id = %s AND is_deleted = 0",
                (user_id, current_user_task_id)
            )
            result = cursor.fetchone()
            if result is None:
                print("No active task found with the given ID.")
                return False
            
            # Update due time only if the task is not deleted
            sql = "UPDATE tasks SET due_time = %s WHERE user_id = %s AND current_user_task_id = %s AND is_deleted = 0"
            cursor.execute(sql, (due_time, user_id, current_user_task_id))
            self.connection.commit()
            affected_rows = cursor.rowcount
            if affected_rows > 0:
                print(f"Selected due time: {due_time} for task ID {current_user_task_id}.")
            else:
                print(f"Failed to update due time for task ID {current_user_task_id}.")
            return affected_rows > 0
        except mysql.connector.Error as err:
            print(f"Error setting task due time: {err}")
            return False
        finally:
            cursor.close()

    def list_active_tasks(self, user_id):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            # Select only active tasks
            sql = "SELECT user_task_id, description, status, due_date, due_time FROM tasks WHERE user_id = %s AND is_deleted = 0 ORDER BY user_task_id"
            cursor.execute(sql, (user_id,))
            tasks = cursor.fetchall()
            return [(index + 1, *task) for index, task in enumerate(tasks)]
        finally:
            cursor.close()

    def get_task(self, user_id, user_task_id):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            sql = "SELECT user_task_id, description, status, due_date, due_time, is_deleted FROM tasks WHERE user_id = %s AND user_task_id = %s"
            cursor.execute(sql, (user_id, user_task_id))
            task = cursor.fetchone()
            if task and not task[5]:  # Check if task is not deleted
                return task
            return None
        finally:
            cursor.close()

    def get_task_due_time(self, user_id, current_user_task_id):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                "SELECT due_time FROM tasks WHERE user_id = %s AND current_user_task_id = %s",
                (user_id, current_user_task_id)
            )
            result = cursor.fetchone()
            if result:
                return result[0]
            return None
        finally:
            cursor.close()

    # Update get_task_details to use current_user_task_id
    def get_task_details(self, user_id, current_user_task_id):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                "SELECT description, is_deleted, due_date, due_time FROM tasks WHERE user_id = %s AND current_user_task_id = %s",
                (user_id, current_user_task_id)
            )
            result = cursor.fetchone()
            if result:
                print(f"Fetched task details: {result}")  # Add this line
                return {
                    'description': result[0],
                    'is_deleted': bool(result[1]),
                    'due_date': result[2],
                    'due_time': result[3]
                }
            print(f"No task found with current_user_task_id: {current_user_task_id}")  # Add this line
            return None
        finally:
            cursor.close()

    # def get_task_details_by_current_user_task_id(self, user_id, current_user_task_id):
    #     self.verify_connection()
    #     cursor = self.connection.cursor()
    #     try:
    #         cursor.execute(
    #             "SELECT description, is_deleted, due_date, due_time FROM tasks WHERE user_id = %s AND current_user_task_id = %s",
    #             (user_id, current_user_task_id)
    #         )
    #         result = cursor.fetchone()
    #         if result:
    #             return {
    #                 'description': result[0],
    #                 'is_deleted': bool(result[1]),
    #                 'due_date': result[2],
    #                 'due_time': result[3],
    #                 'current_user_task_id': current_user_task_id
    #             }
    #         return None
    #     finally:
    #         cursor.close()

    # Update the get_task_details_by_current_user_task_id method to fetch the updated_on timestamp
    def get_task_details_by_current_user_task_id(self, user_id, current_user_task_id):
        self.verify_connection()
        cursor = self.connection.cursor(dictionary=True)  # Using dictionary cursor to fetch results as dictionaries
        try:
            cursor.execute(
                "SELECT current_user_task_id, description, status, due_date, due_time, updated_on, is_deleted FROM tasks WHERE user_id = %s AND current_user_task_id = %s AND is_deleted = 0",
                (user_id, current_user_task_id)
            )
            result = cursor.fetchone()
            if result:
                print("Fetched task details:", result)  # Debugging output
                return {
                    'description': result['description'],
                    'status': result['status'],
                    'due_date': result['due_date'],
                    'due_time': result['due_time'],
                    'updated_on': result['updated_on'],
                    'is_deleted': result['is_deleted']
                }
            else:
                print("No task found with ID:", current_user_task_id)  # Debugging output
                return None
        finally:
            cursor.close()

    def get_current_user_task_id(self, user_id, user_task_id):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            sql = "SELECT current_user_task_id FROM tasks WHERE user_id = %s AND user_task_id = %s"
            cursor.execute(sql, (user_id, user_task_id))
            result = cursor.fetchone()
            if result:
                return result[0]
            return None
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

    def search_tasks_full_details(self, user_id):
        self.verify_connection()
        cursor = self.connection.cursor(dictionary=True)
        query = """
        SELECT current_user_task_id, description, status, due_date, due_time FROM tasks 
        WHERE user_id = %s AND due_date IS NOT NULL AND is_deleted = 0
        ORDER BY due_date
        """
        cursor.execute(query, (user_id,))
        result = cursor.fetchall()
        cursor.close()
        return result

    def search_tasks_by_description(self, user_id, search_term):
        cursor = self.connection.cursor(dictionary=True)
        query = """
        SELECT current_user_task_id, description, status FROM tasks 
        WHERE user_id = %s AND LOWER(description) LIKE %s AND is_deleted = 0
        ORDER BY current_user_task_id
        """
        search_like = f"%{search_term}%"
        cursor.execute(query, (user_id, search_like))
        result = cursor.fetchall()
        cursor.close()
        return result
    
    def check_task_exists(self, user_id, current_user_task_id):
        """ Check if the task exists and is not marked as deleted. """
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            cursor.execute("""
                SELECT 1 FROM tasks 
                WHERE user_id = %s AND current_user_task_id = %s AND is_deleted = 0
            """, (user_id, current_user_task_id))
            return cursor.fetchone() is not None
        finally:
            cursor.close()

    def check_and_print_task_details(self, user_id, task_id):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            cursor.execute("SELECT * FROM tasks WHERE user_id = %s AND current_user_task_id = %s", (user_id, task_id))
            task = cursor.fetchone()
            if task:
                print("Task Details:", task)
            else:
                print("No task found with ID:", task_id)
        except mysql.connector.Error as err:
            print("Error fetching task details:", err)
        finally:
            cursor.close()

    # def get_upcoming_reminders(self):
    #     self.verify_connection()
    #     cursor = self.connection.cursor(dictionary=True)
    #     try:
    #         sql = "SELECT * FROM reminders WHERE reminded = FALSE AND reminder_time <= NOW()"
    #         cursor.execute(sql)
    #         return cursor.fetchall()
    #     finally:
    #         cursor.close()

    # def mark_reminder_as_sent(self, reminder_id):
    #     self.verify_connection()
    #     cursor = self.connection.cursor()
    #     try:
    #         sql = "UPDATE reminders SET reminded = TRUE WHERE id = %s"
    #         cursor.execute(sql, (reminder_id,))
    #         self.connection.commit()
    #     finally:
    #         cursor.close()

    # def list_tasks_for_reminders(self, user_id):
    #     self.verify_connection()
    #     cursor = self.connection.cursor(dictionary=True)  # Ensure results are returned as dictionaries
    #     try:
    #         # Fetch only active tasks with a due date and due time set
    #         sql = "SELECT current_user_task_id, description, status, due_date, due_time FROM tasks WHERE user_id = %s AND is_deleted = 0 ORDER BY current_user_task_id"
    #         cursor.execute(sql, (user_id,))
    #         tasks = cursor.fetchall()
    #         return tasks
    #     finally:
    #         cursor.close()

    def list_tasks_for_reminders(self, user_id):
        self.verify_connection()
        cursor = self.connection.cursor(dictionary=True)
        try:
            # Fetch all active tasks
            sql = "SELECT current_user_task_id, description, status FROM tasks WHERE user_id = %s AND is_deleted = 0 ORDER BY current_user_task_id"
            cursor.execute(sql, (user_id,))
            tasks = cursor.fetchall()
            return tasks
        finally:
            cursor.close()

    # def add_reminder(self, user_id, task_id, reminder_time, current_user_task_id):
    #     self.verify_connection()
    #     cursor = self.connection.cursor()
    #     try:
    #         # SQL command that either inserts a new record or updates the existing one
    #         sql = """
    #         INSERT INTO reminders (user_id, task_id, reminder_time, current_user_task_id, reminded)
    #         VALUES (%s, %s, %s, %s, 0)
    #         ON DUPLICATE KEY UPDATE
    #         reminder_time = VALUES(reminder_time), current_user_task_id = VALUES(current_user_task_id), updated_on = NOW();
    #         """
    #         cursor.execute(sql, (user_id, task_id, reminder_time, current_user_task_id))
    #         self.connection.commit()
    #         print(f"Reminder added or updated for task_id: {task_id}, user_id: {user_id}")
    #     except mysql.connector.Error as error:
    #         print(f"Failed to add or update reminder: {error}")
    #         self.connection.rollback()
    #     finally:
    #         cursor.close()

    def add_reminder(self, user_id, task_id, reminder_date, reminder_time, current_user_task_id):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            # Prepare the SQL statement with logging
            sql_insert = """
            INSERT INTO reminders (user_id, task_id, reminder_date, reminder_time, current_user_task_id, reminded)
            VALUES (%s, %s, %s, %s, %s, 0)
            """
            sql_update = """
            ON DUPLICATE KEY UPDATE
            reminder_date = VALUES(reminder_date),
            reminder_time = VALUES(reminder_time),
            current_user_task_id = VALUES(current_user_task_id),
            reminded = 0
            """
            print(f"Executing SQL: {sql_insert} {sql_update}")
            print(f"With values: {user_id}, {task_id}, {reminder_date}, {reminder_time}, {current_user_task_id}")
            # Execute the SQL command
            cursor.execute(sql_insert + sql_update, (user_id, task_id, reminder_date, reminder_time, current_user_task_id))
            self.connection.commit()  # Commit the changes to the database
            print("SQL Execution successful, changes committed.")
        except Exception as e:
            self.connection.rollback()  # Roll back in case of error
            print(f"Error executing SQL: {e}")
            raise e
        finally:
            cursor.close()

    # Add the method to fetch reminder updated_on time from reminders table
    def get_reminder_updated_on(self, user_id, task_id):
        self.verify_connection()
        cursor = self.connection.cursor(dictionary=True)
        try:
            sql = "SELECT updated_on FROM reminders WHERE user_id = %s AND task_id = %s"
            cursor.execute(sql, (user_id, task_id))
            return cursor.fetchone()
        finally:
            cursor.close()

    def get_current_user_task_id_from_tasks(self, user_id, current_user_task_id):
        self.verify_connection()
        cursor = self.connection.cursor(dictionary=True)
        try:
            sql = """
            SELECT * FROM tasks
            WHERE user_id = %s
            AND current_user_task_id = %s
            AND is_deleted = 0
            AND current_user_task_id IS NOT NULL
            """
            cursor.execute(sql, (user_id, current_user_task_id))
            task_details = cursor.fetchone()
            cursor.fetchall()  # Ensure all results are consumed
            return task_details
        finally:
            cursor.close()

    def get_due_reminders(self, current_time):
        self.verify_connection()
        cursor = self.connection.cursor(dictionary=True)
        try:
            sql = "SELECT * FROM reminders WHERE reminded = FALSE AND reminder_date <= %s AND reminder_time <= %s"
            cursor.execute(sql, (current_time.date(), current_time.time()))
            return cursor.fetchall()
        finally:
            cursor.close()

    def mark_reminder_as_sent(self, reminder_id):
        self.verify_connection()
        cursor = self.connection.cursor()
        try:
            sql = "UPDATE reminders SET reminded = TRUE WHERE id = %s"
            cursor.execute(sql, (reminder_id,))
            self.connection.commit()
        finally:
            cursor.close()