import unittest
from unittest.mock import patch
import os
from shokobridge.file_manager import FileManager

class TestFileManager(unittest.TestCase):

    def setUp(self):
        """Set up a mock config and FileManager instances for each test."""
        self.mock_config = {
            'options': {
                'link_type': 'symlink',
                'use_relative_symlinks': False
            },
            'path_mappings': []
        }
        # Standard file manager for testing real operations (with mocks)
        self.file_manager = FileManager(self.mock_config, dry_run=False)
        # Dry run file manager for testing dry run logic
        self.file_manager_dry_run = FileManager(self.mock_config, dry_run=True)

    @patch('shokobridge.file_manager.shutil')
    @patch('shokobridge.file_manager.os')
    def test_link_single_file_dry_run(self, mock_os, mock_shutil):
        """Test that in dry_run mode, no filesystem operations are performed."""
        # Ensure the file doesn't "exist" so we don't skip the logic
        mock_os.path.exists.return_value = False
        
        source = "/source/file.mkv"
        dest = "/dest/file.mkv"

        # Call the method on the dry_run instance
        result = self.file_manager_dry_run._link_single_file(source, dest)

        # Assert that the method returns True (as it would succeed in a real run)
        self.assertTrue(result)

        # Assert that no file-modifying functions were called
        mock_os.makedirs.assert_not_called()
        mock_os.symlink.assert_not_called()
        mock_os.link.assert_not_called()
        mock_shutil.copy2.assert_not_called()
        mock_shutil.move.assert_not_called()

    @patch('shokobridge.file_manager.shutil')
    @patch('shokobridge.file_manager.os')
    def test_link_single_file_symlink(self, mock_os, mock_shutil):
        """Test that the symlink operation calls the correct os functions."""
        # Ensure the file doesn't "exist" to trigger the linking logic
        mock_os.path.exists.return_value = False
        # Mock the relpath to return a predictable value for the target calculation
        mock_os.path.relpath.return_value = "../source/file.mkv"
        # Mock dirname to get the parent directory for makedirs
        mock_os.path.dirname.return_value = "/dest"

        source = "/source/file.mkv"
        dest = "/dest/file.mkv"

        # Call the method on the standard (non-dry-run) instance
        result = self.file_manager._link_single_file(source, dest)

        self.assertTrue(result)
        # Verify the destination directory was created
        mock_os.makedirs.assert_called_once_with("/dest", exist_ok=True)
        # Verify symlink was called with the correct source and destination
        mock_os.symlink.assert_called_once_with(source, dest)

    @patch('shokobridge.file_manager.shutil')
    @patch('shokobridge.file_manager.os')
    def test_link_single_file_hardlink(self, mock_os, mock_shutil):
        """Test that the hardlink operation calls the correct os functions."""
        # Create a file manager specifically for hardlinking
        mock_config = self.mock_config.copy()
        mock_config['options']['link_type'] = 'hardlink'
        file_manager_hardlink = FileManager(mock_config, dry_run=False)

        # Ensure the file doesn't "exist" to trigger the linking logic
        mock_os.path.exists.return_value = False
        # Mock dirname to get the parent directory for makedirs
        mock_os.path.dirname.return_value = "/dest"

        source = "/source/file.mkv"
        dest = "/dest/file.mkv"

        result = file_manager_hardlink._link_single_file(source, dest)

        self.assertTrue(result)
        mock_os.makedirs.assert_called_once_with("/dest", exist_ok=True)
        mock_os.link.assert_called_once_with(source, dest)
        mock_os.symlink.assert_not_called()

    @patch('shokobridge.file_manager.shutil')
    @patch('shokobridge.file_manager.os')
    def test_link_single_file_copy(self, mock_os, mock_shutil):
        """Test that the copy operation calls the correct shutil function."""
        # Create a file manager specifically for copying
        mock_config = self.mock_config.copy()
        mock_config['options']['link_type'] = 'copy'
        file_manager_copy = FileManager(mock_config, dry_run=False)

        # Ensure the file doesn't "exist" to trigger the linking logic
        mock_os.path.exists.return_value = False
        mock_os.path.dirname.return_value = "/dest"

        source = "/source/file.mkv"
        dest = "/dest/file.mkv"

        result = file_manager_copy._link_single_file(source, dest)

        self.assertTrue(result)
        mock_os.makedirs.assert_called_once_with("/dest", exist_ok=True)
        mock_shutil.copy2.assert_called_once_with(source, dest)

    @patch('shokobridge.file_manager.shutil')
    @patch('shokobridge.file_manager.os')
    def test_link_single_file_move(self, mock_os, mock_shutil):
        """Test that the move operation calls the correct shutil function."""
        # Create a file manager specifically for moving
        mock_config = self.mock_config.copy()
        mock_config['options']['link_type'] = 'move'
        file_manager_move = FileManager(mock_config, dry_run=False)

        # Ensure the file doesn't "exist" to trigger the linking logic
        mock_os.path.exists.return_value = False
        mock_os.path.dirname.return_value = "/dest"

        source = "/source/file.mkv"
        dest = "/dest/file.mkv"

        result = file_manager_move._link_single_file(source, dest)

        self.assertTrue(result)
        mock_os.makedirs.assert_called_once_with("/dest", exist_ok=True)
        mock_shutil.move.assert_called_once_with(source, dest)

    def test_calculate_symlink_target(self):
        """Test the logic for calculating the symlink target path."""
        source = "/media/anime/series/episode.mkv"
        dest = "/plex/shows/series/season/episode.mkv"

        with self.subTest("absolute symlink (default)"):
            fm = FileManager({'options': {'use_relative_symlinks': False}, 'path_mappings': []}, dry_run=False)
            target = fm._calculate_symlink_target(source, dest)
            self.assertEqual(target, source)

        with self.subTest("relative symlink"):
            fm = FileManager({'options': {'use_relative_symlinks': True}, 'path_mappings': []}, dry_run=False)
            with patch('shokobridge.file_manager.os.path.relpath') as mock_relpath:
                mock_relpath.return_value = "../../../../media/anime/series/episode.mkv"
                target = fm._calculate_symlink_target(source, dest)
                mock_relpath.assert_called_once_with(source, start=os.path.dirname(dest))
                self.assertEqual(target, "../../../../media/anime/series/episode.mkv")

        with self.subTest("absolute symlink with path mapping"):
            config = {
                'options': {'use_relative_symlinks': False},
                'path_mappings': [{'script_path': '/media/anime/', 'plex_path': '/share/anime/'}]
            }
            fm = FileManager(config, dry_run=False)
            target = fm._calculate_symlink_target(source, dest)
            self.assertEqual(target, "/share/anime/series/episode.mkv")

        with self.subTest("relative symlink with path mapping (should be absolute)"):
            config = {
                'options': {'use_relative_symlinks': True},
                'path_mappings': [{'script_path': '/media/anime/', 'plex_path': '/share/anime/'}]
            }
            fm = FileManager(config, dry_run=False)
            target = fm._calculate_symlink_target(source, dest)
            self.assertEqual(target, "/share/anime/series/episode.mkv")

    @patch('shokobridge.file_manager.os')
    def test_find_supplemental_files(self, mock_os):
        """Test finding supplemental files and directory caching."""
        media_file = "/source/dir/episode.mkv"
        mock_os.path.exists.return_value = True
        mock_os.path.dirname.return_value = "/source/dir"
        mock_os.path.basename.return_value = "episode.mkv"
        mock_os.path.splitext.side_effect = [("episode", ".mkv"), ("unrelated", ".txt")]
        mock_os.listdir.return_value = [
            "episode.mkv",
            "episode.eng.srt",
            "unrelated.txt"
        ]
        mock_os.path.join.return_value = "/source/dir/episode.eng.srt"

        dir_cache = {}
        # First call should populate the cache
        supp_files = self.file_manager.find_supplemental_files(media_file, dir_cache)
        # Second call should use the cache
        self.file_manager.find_supplemental_files(media_file, dir_cache)

        mock_os.listdir.assert_called_once_with("/source/dir")
        self.assertEqual(len(supp_files), 1)
        self.assertEqual(supp_files[0], ("/source/dir/episode.eng.srt", ".eng.srt"))

    @patch('shokobridge.file_manager.os')
    def test_process_file_group(self, mock_os):
        """Test processing a group of files, including success and rollback scenarios."""
        source_file = "/source/dir/episode.mkv"
        dest_file = "/dest/dir/episode.mkv"
        supp_source_file = "/source/dir/episode.eng.srt"
        supp_dest_file = "/dest/dir/episode.eng.srt"

        with self.subTest("successful processing"):
            # Mock the internal methods of the file_manager instance for this subtest
            self.file_manager.find_supplemental_files = unittest.mock.Mock(
                return_value=[(supp_source_file, ".eng.srt")]
            )
            self.file_manager._link_single_file = unittest.mock.Mock(return_value=True)
            mock_os.path.splitext.return_value = ("/dest/dir/episode", ".mkv")

            result = self.file_manager.process_file_group(source_file, dest_file, {})

            self.assertTrue(result)
            self.assertEqual(self.file_manager._link_single_file.call_count, 2)
            self.file_manager._link_single_file.assert_any_call(source_file, dest_file)
            self.file_manager._link_single_file.assert_any_call(supp_source_file, supp_dest_file)
            mock_os.remove.assert_not_called()

        # Reset mocks for the next subtest
        self.setUp()
        mock_os.reset_mock()

        with self.subTest("rollback on failure"):
            self.file_manager.find_supplemental_files = unittest.mock.Mock(return_value=[(supp_source_file, ".eng.srt")])
            # Simulate main file succeeding, but supplemental failing
            self.file_manager._link_single_file = unittest.mock.Mock(side_effect=[True, False])
            mock_os.path.splitext.return_value = ("/dest/dir/episode", ".mkv")
            mock_os.path.basename.return_value = "episode.mkv" # Configure basename for logging
            mock_os.path.exists.return_value = True # For the rollback check

            # Use assertLogs to capture and verify the log output, preventing it from going to the console
            with self.assertLogs('root', level='ERROR') as cm:
                result = self.file_manager.process_file_group(source_file, dest_file, {})
                self.assertIn("FAILED to process a file in the group for 'episode.mkv'", cm.output[0])

            self.assertFalse(result)
            self.assertEqual(self.file_manager._link_single_file.call_count, 2)
            # Assert that we tried to remove the successfully linked file
            mock_os.remove.assert_called_once_with(dest_file)

    @patch('shokobridge.file_manager.os')
    def test_cleanup_stale_files(self, mock_os):
        """Test cleanup of stale files and their supplemental files."""
        dest_path = "/dest/dir/stale_episode.mkv"
        stale_files_in_dir = [
            "stale_episode.mkv",
            "stale_episode.eng.srt",
            "another_file.mkv"
        ]

        with self.subTest("normal cleanup"):
            mock_os.path.exists.return_value = True
            mock_os.path.dirname.return_value = "/dest/dir"
            mock_os.path.basename.return_value = "stale_episode.mkv"
            mock_os.path.splitext.side_effect = lambda p: os.path.splitext(p)
            mock_os.listdir.return_value = stale_files_in_dir
            mock_os.path.join.side_effect = lambda *args: os.path.join(*args)

            self.file_manager.cleanup_stale_files(dest_path)

            self.assertEqual(mock_os.remove.call_count, 2)
            mock_os.remove.assert_any_call("/dest/dir/stale_episode.mkv")
            mock_os.remove.assert_any_call("/dest/dir/stale_episode.eng.srt")

        # Reset mocks for the next subtest
        mock_os.reset_mock()

        with self.subTest("dry run cleanup"):
            mock_os.path.exists.return_value = True
            mock_os.path.dirname.return_value = "/dest/dir"
            mock_os.path.basename.return_value = "stale_episode.mkv"
            mock_os.listdir.return_value = stale_files_in_dir

            self.file_manager_dry_run.cleanup_stale_files(dest_path)

            mock_os.remove.assert_not_called()

    @patch('shokobridge.file_manager.os')
    def test_cleanup_empty_dirs(self, mock_os):
        """Test the cleanup of empty directories."""
        root_dir = "/dest"
        # os.walk yields (dirpath, dirnames, filenames) from the bottom up.
        walk_data = [
            ('/dest/series/season/extra', [], ['file.txt']),
            ('/dest/series/season/empty', [], []),
            ('/dest/series/season', ['extra', 'empty'], []),
            ('/dest/series', ['season'], []),
            ('/dest', ['series'], ['some_other_file.txt'])
        ]

        with self.subTest("normal cleanup"):
            mock_os.walk.return_value = walk_data
            self.file_manager.cleanup_empty_dirs(root_dir)
            mock_os.walk.assert_called_once_with(root_dir, topdown=False)
            mock_os.rmdir.assert_called_once_with('/dest/series/season/empty')

        mock_os.reset_mock()

        with self.subTest("dry run cleanup"):
            self.file_manager_dry_run.cleanup_empty_dirs(root_dir)
            mock_os.walk.assert_not_called()
            mock_os.rmdir.assert_not_called()

if __name__ == '__main__':
    unittest.main()