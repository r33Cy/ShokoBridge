import unittest
import sqlite3
from shokobridge.database import DatabaseManager

class TestDatabaseManager(unittest.TestCase):

    def setUp(self):
        """Set up a new in-memory database for each test."""
        # Using :memory: for the db_path creates a temporary in-memory database
        self.db_path = ":memory:"
        self.db_manager = DatabaseManager(self.db_path)
        # The setup method is called to ensure the table exists for each test
        self.db_manager.setup()

    def tearDown(self):
        """Close the database connection after each test."""
        self.db_manager.close_connection()

    def test_add_and_get_processed_file(self):
        """Test adding a file and retrieving it."""
        shoko_file_id = 123
        destination_path = "/plex/shows/series/s01e01.mkv"

        # Add the file
        self.db_manager.add_processed_file(shoko_file_id, destination_path)

        # Get all processed IDs
        processed_ids = self.db_manager.get_processed_file_ids()

        # Assert that the added ID is in the set and the set size is correct
        self.assertIn(shoko_file_id, processed_ids)
        self.assertEqual(len(processed_ids), 1)

    def test_get_stale_entries(self):
        """Test identifying stale entries in the database."""
        # Add some files to the database
        self.db_manager.add_processed_file(101, "/path/to/file1.mkv")
        self.db_manager.add_processed_file(102, "/path/to/file2.mkv") # This one will be stale
        self.db_manager.add_processed_file(103, "/path/to/file3.mkv")

        # Simulate the current list of file IDs from Shoko
        current_shoko_ids = [101, 103, 104]

        # Get stale entries
        stale_entries = self.db_manager.get_stale_entries(current_shoko_ids)

        # Assert that only the stale entry is returned
        self.assertEqual(len(stale_entries), 1)
        self.assertEqual(stale_entries[0]['shoko_file_id'], 102)
        self.assertEqual(stale_entries[0]['destination_path'], "/path/to/file2.mkv")

    def test_remove_stale_entry(self):
        """Test removing a stale entry from the database."""
        # Add some files
        self.db_manager.add_processed_file(201, "/path/file_a.mkv")
        self.db_manager.add_processed_file(202, "/path/file_b.mkv") # To be removed

        # Remove one entry
        self.db_manager.remove_stale_entry(202)

        # Get the remaining processed IDs
        processed_ids = self.db_manager.get_processed_file_ids()

        # Assert that the correct entry was removed
        self.assertEqual(len(processed_ids), 1)
        self.assertIn(201, processed_ids)
        self.assertNotIn(202, processed_ids)

if __name__ == '__main__':
    unittest.main()