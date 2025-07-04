# shokobridge/database.py
import logging
import sqlite3

class DatabaseManager:
    """Manages all interactions with the SQLite database."""

    def __init__(self, db_path):
        """
        Initializes the DatabaseManager.

        :param db_path: The path to the SQLite database file.
        """
        self.db_path = db_path
        self.conn = None
        logging.debug("DatabaseManager initialized for path: %s", self.db_path)

    def _get_connection(self):
        """Establishes and returns a database connection."""
        if self.conn is None:
            try:
                self.conn = sqlite3.connect(self.db_path)
                # Use Row factory to access columns by name
                self.conn.row_factory = sqlite3.Row
            except sqlite3.Error as e:
                logging.critical("Could not connect to database at %s. Error: %s", self.db_path, e)
                raise
        return self.conn

    def close_connection(self):
        """Closes the database connection if it's open."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logging.debug("Database connection closed.")

    def setup(self):
        """Creates the necessary tables if they don't exist."""
        logging.debug("Setting up database schema...")
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processed_files (
                    shoko_file_id INTEGER PRIMARY KEY,
                    destination_path TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            logging.info("Database initialized successfully.")
        except sqlite3.Error as e:
            logging.critical("Database setup failed: %s", e)
            raise

    def get_processed_file_ids(self):
        """Fetches a set of all processed Shoko file IDs."""
        logging.debug("Loading processed file IDs from database.")
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT shoko_file_id FROM processed_files")
            ids = {row['shoko_file_id'] for row in cursor.fetchall()}
            logging.debug("Loaded %d processed file IDs.", len(ids))
            return ids
        except sqlite3.Error as e:
            logging.error("Failed to get processed file IDs from database. Error: %s", e)
            return set()

    def add_processed_file(self, shoko_file_id, destination_path):
        """Adds a record for a newly processed file."""
        logging.debug("Adding file ID %d to database.", shoko_file_id)
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO processed_files (shoko_file_id, destination_path) VALUES (?, ?)",
                           (shoko_file_id, destination_path))
            conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error("Failed to add file ID %d to database. Error: %s", shoko_file_id, e)
            return False

    def get_stale_entries(self, all_shoko_file_ids):
        """Compares DB entries with current Shoko file IDs to find stale ones."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT shoko_file_id, destination_path FROM processed_files")
        db_files = cursor.fetchall()
        current_ids_set = set(all_shoko_file_ids)
        return [entry for entry in db_files if entry['shoko_file_id'] not in current_ids_set]

    def remove_stale_entry(self, shoko_file_id):
        """Removes a stale entry from the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM processed_files WHERE shoko_file_id = ?", (shoko_file_id,))
        conn.commit()