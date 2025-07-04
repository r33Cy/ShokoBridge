import unittest
from unittest.mock import patch, MagicMock, ANY

# The class under test is in shokobridge/bridge.py
from shokobridge.bridge import ShokoBridge

class TestShokoBridge(unittest.TestCase):

    # Patch dependencies where they are used: in 'shokobridge.bridge'
    @patch('shokobridge.bridge.TMDbClient')
    @patch('shokobridge.bridge.ShokoClient')
    @patch('shokobridge.bridge.FileManager')
    @patch('shokobridge.bridge.DatabaseManager')
    # Patch the static method for cleaning filenames
    @patch('shokobridge.bridge.ShokoBridge._clean_filename', side_effect=lambda x: x)
    # Patch the WSL host IP check as it's an external call
    @patch('shokobridge.bridge.get_windows_host_ip', return_value='127.0.0.1')
    # Patch the directory existence check to prevent early exit
    @patch('shokobridge.bridge.os.path.isdir', return_value=True)
    def test_run_add_update_single_tv_show_file(self, mock_isdir, mock_get_ip, mock_clean_filename,
                                                mock_db_manager, mock_file_manager,
                                                mock_shoko_client, mock_tmdb_client):
        """
        Test a standard run with one new TV show file to process successfully.
        """
        # --- Arrange ---
        # Mock arguments to simulate a standard run
        mock_args = MagicMock()
        mock_args.cleanup = False
        mock_args.dry_run = False
        mock_args.debug = False

        # A more complete mock config, reflecting the structure of config.json
        # plus the 'paths' key injected by the main script.
        mock_config = {
            'directories': {
                'source_root': '/source',
                'destination': '/dest/shows',
            },
            'shoko': {'url': 'http://test.host:8111', 'api_key': 'test_key'},
            'tmdb': {'api_key': 'test_key'},
            'path_mappings': [],
            'options': {
                'title_similarity_threshold': 0.85,
                'link_type': 'symlink', 'use_relative_symlinks': False
            },
            'paths': {
                'db': 'test.db',
                'cache': 'cache.json',
                'unmatched_report': 'report.txt'
            }
        }

        # Get mock instances of the clients and managers
        db_manager = mock_db_manager.return_value
        file_manager = mock_file_manager.return_value
        shoko_client = mock_shoko_client.return_value
        tmdb_client = mock_tmdb_client.return_value

        # Simulate no files processed yet
        db_manager.get_processed_file_ids.return_value = set()
        # Shoko has one file
        shoko_client.get_all_file_ids.return_value = [123]
        # Simulate successful connection
        shoko_client.check_connection.return_value = True

        # Mock API responses based on the structure used in bridge.py
        shoko_client.get_file_details.return_value = {
            'Locations': [{'RelativePath': 'series/episode.mkv'}],
            'SeriesIDs': [{'SeriesID': {'TMDB': {'Show': [999]}}, 'EpisodeIDs': [{'ID': 456}]}]
        }
        shoko_client.get_episode_details.return_value = {
            'Name': 'Episode Title',
            'AniDB': {'Type': 'Normal'},
            'IDs': {'TMDB': {'Episode': [789]}},
            'TMDB': {'Episodes': [{
                'ID': 789,
                'Title': 'Episode Title',
                'SeasonNumber': 1,
                'EpisodeNumber': 1
            }]}
        }
        tmdb_client.get_series_details.return_value = {
            'name': 'Series Title',
            'first_air_date': '2023-01-01'
        }
        # Simulate successful file processing
        file_manager.process_file_group.return_value = True

        # --- Act ---
        # Instantiate the bridge with our mock objects
        bridge = ShokoBridge(mock_args, mock_config)
        # The run method will use the mocked components
        bridge.run()

        # --- Assert ---
        # Verify the main sequence of events
        shoko_client.check_connection.assert_called_once()
        db_manager.get_processed_file_ids.assert_called_once()
        shoko_client.get_all_file_ids.assert_called_once()
        shoko_client.get_file_details.assert_called_once_with(123)
        shoko_client.get_episode_details.assert_called_once_with(456)
        tmdb_client.get_series_details.assert_called_once_with(999)

        # Verify the path construction and file processing calls
        expected_dest_path = '/dest/shows/Series Title (2023)/Season 01/Series Title (2023) - S01E01 - Episode Title.mkv'
        file_manager.process_file_group.assert_called_once_with('/source/series/episode.mkv', expected_dest_path, ANY)
        db_manager.add_processed_file.assert_called_once_with(123, expected_dest_path)

    @patch('shokobridge.bridge.TMDbClient')
    @patch('shokobridge.bridge.ShokoClient')
    @patch('shokobridge.bridge.FileManager')
    @patch('shokobridge.bridge.DatabaseManager')
    @patch('shokobridge.bridge.ShokoBridge._clean_filename', side_effect=lambda x: x)
    @patch('shokobridge.bridge.get_windows_host_ip', return_value='127.0.0.1')
    @patch('shokobridge.bridge.os.path.isdir', return_value=True)
    def test_run_add_update_single_movie_file(self, mock_isdir, mock_get_ip, mock_clean_filename,
                                               mock_db_manager, mock_file_manager,
                                               mock_shoko_client, mock_tmdb_client):
        """
        Test a standard run with one new movie file to process successfully.
        """
        # --- Arrange ---
        mock_args = MagicMock()
        mock_args.cleanup = False
        mock_args.dry_run = False
        mock_args.debug = False

        # Mock config with a separate movie destination
        mock_config = {
            'directories': {
                'source_root': '/source',
                'destination': '/dest/shows',
                'destination_movies': '/dest/movies'
            },
            'shoko': {'url': 'http://test.host:8111', 'api_key': 'test_key'},
            'tmdb': {'api_key': 'test_key'},
            'path_mappings': [],
            'options': {
                'title_similarity_threshold': 0.85,
                'link_type': 'symlink', 'use_relative_symlinks': False
            },
            'paths': {
                'db': 'test.db',
                'cache': 'cache.json',
                'unmatched_report': 'report.txt'
            }
        }

        db_manager = mock_db_manager.return_value
        file_manager = mock_file_manager.return_value
        shoko_client = mock_shoko_client.return_value
        tmdb_client = mock_tmdb_client.return_value

        db_manager.get_processed_file_ids.return_value = set()
        shoko_client.get_all_file_ids.return_value = [123]
        shoko_client.check_connection.return_value = True

        # Mock API responses for a MOVIE
        shoko_client.get_file_details.return_value = {
            'Locations': [{'RelativePath': 'movies/movie.mkv'}],
            'SeriesIDs': [{'EpisodeIDs': [{'ID': 456}]}]
        }
        shoko_client.get_episode_details.return_value = {
            'Name': 'Movie Title', 'AniDB': {'Type': 'Movie'},
            'IDs': {'TMDB': {'Movie': [98765]}},
            'TMDB': {'Movies': [{'ID': 98765, 'Title': 'Movie Title from TMDb', 'ReleasedAt': '2024-01-01'}]}
        }
        file_manager.process_file_group.return_value = True

        # --- Act ---
        bridge = ShokoBridge(mock_args, mock_config)
        bridge.run()

        # --- Assert ---
        tmdb_client.get_series_details.assert_not_called()
        tmdb_client.get_movie_details.assert_not_called()

        expected_dest_path = '/dest/movies/Movie Title from TMDb (2024)/Movie Title from TMDb (2024).mkv'
        file_manager.process_file_group.assert_called_once_with('/source/movies/movie.mkv', expected_dest_path, ANY)
        db_manager.add_processed_file.assert_called_once_with(123, expected_dest_path)

    @patch('shokobridge.bridge.TMDbClient')
    @patch('shokobridge.bridge.ShokoClient')
    @patch('shokobridge.bridge.FileManager')
    @patch('shokobridge.bridge.DatabaseManager')
    @patch('shokobridge.bridge.get_windows_host_ip', return_value='127.0.0.1')
    @patch('shokobridge.bridge.os.path.isdir', return_value=True)
    def test_run_cleanup_stale_files(self, mock_isdir, mock_get_ip,
                                     mock_db_manager, mock_file_manager,
                                     mock_shoko_client, mock_tmdb_client):
        """
        Test a cleanup run where one stale file is found and removed.
        """
        # --- Arrange ---
        # Mock arguments to simulate a cleanup run
        mock_args = MagicMock()
        mock_args.cleanup = True
        mock_args.dry_run = False
        mock_args.debug = False

        # Mock config
        mock_config = {
            'directories': {
                'source_root': '/source',
                'destination': '/dest/shows',
                'destination_movies': '/dest/movies'
            },
            'shoko': {'url': 'http://test.host:8111', 'api_key': 'test_key'},
            'tmdb': {'api_key': 'test_key'},
            'path_mappings': [],
            'options': {
                'link_type': 'symlink',
                'use_relative_symlinks': False
            },
            'paths': {
                'db': 'test.db',
                'cache': 'cache.json',
                'unmatched_report': 'report.txt'
            }
        }

        db_manager = mock_db_manager.return_value
        file_manager = mock_file_manager.return_value
        shoko_client = mock_shoko_client.return_value

        # Shoko has no files, but our DB has one, making it stale.
        shoko_client.get_all_file_ids.return_value = []
        db_manager.get_stale_entries.return_value = [
            {'shoko_file_id': 999, 'destination_path': '/dest/shows/Stale Show/S01/stale.mkv'}
        ]
        shoko_client.check_connection.return_value = True

        # --- Act ---
        bridge = ShokoBridge(mock_args, mock_config)
        bridge.run()

        # --- Assert ---
        shoko_client.check_connection.assert_called_once()
        db_manager.get_stale_entries.assert_called_once_with([])
        file_manager.cleanup_stale_files.assert_called_once_with('/dest/shows/Stale Show/S01/stale.mkv')
        db_manager.remove_stale_entry.assert_called_once_with(999)
        file_manager.cleanup_empty_dirs.assert_any_call('/dest/shows')
        file_manager.cleanup_empty_dirs.assert_any_call('/dest/movies')
        self.assertEqual(file_manager.cleanup_empty_dirs.call_count, 2)

    @patch('shokobridge.bridge.open', new_callable=unittest.mock.mock_open)
    @patch('shokobridge.bridge.TMDbClient')
    @patch('shokobridge.bridge.ShokoClient')
    @patch('shokobridge.bridge.FileManager')
    @patch('shokobridge.bridge.DatabaseManager')
    @patch('shokobridge.bridge.ShokoBridge._clean_filename', side_effect=lambda x: x)
    @patch('shokobridge.bridge.get_windows_host_ip', return_value='127.0.0.1')
    @patch('shokobridge.bridge.os.path.isdir', return_value=True)
    def test_run_unmatched_file(self, mock_isdir, mock_get_ip, mock_clean_filename,
                                mock_db_manager, mock_file_manager,
                                mock_shoko_client, mock_tmdb_client, mock_open):
        """
        Test a run where a file cannot be matched and is added to the report.
        """
        # --- Arrange ---
        mock_args = MagicMock()
        mock_args.cleanup = False
        mock_args.dry_run = False
        mock_args.debug = False

        mock_config = {
            'directories': {
                'source_root': '/source',
                'destination': '/dest/shows',
            },
            'shoko': {'url': 'http://test.host:8111', 'api_key': 'test_key'},
            'tmdb': {'api_key': 'test_key'},
            'path_mappings': [],
            'options': {
                'title_similarity_threshold': 0.85,
                'link_type': 'symlink', 'use_relative_symlinks': False
            },
            'paths': {
                'db': 'test.db',
                'cache': 'cache.json',
                'unmatched_report': 'report.txt'
            }
        }

        db_manager = mock_db_manager.return_value
        file_manager = mock_file_manager.return_value
        shoko_client = mock_shoko_client.return_value
        tmdb_client = mock_tmdb_client.return_value

        db_manager.get_processed_file_ids.return_value = set()
        shoko_client.get_all_file_ids.return_value = [123]
        shoko_client.check_connection.return_value = True

        # Mock API responses for a file that CANNOT be matched
        shoko_client.get_file_details.return_value = {
            'Locations': [{'RelativePath': 'series/unmatched_episode.mkv'}],
            'SeriesIDs': [{'SeriesID': {'TMDB': {'Show': [999]}}, 'EpisodeIDs': [{'ID': 456}]}]
        }
        # No TMDb episode ID, forcing a title match which will fail
        shoko_client.get_episode_details.return_value = {
            'Name': 'A Very Unique Title That Will Not Match', 'AniDB': {'Type': 'Normal'}, 'IDs': {'TMDB': {}}
        }
        tmdb_client.get_series_details.return_value = {'name': 'Series Title', 'first_air_date': '2023-01-01', 'seasons': []}

        # --- Act & Assert Logs ---
        # Use assertLogs to capture and verify the expected warning messages,
        # which also prevents them from printing to the console during tests.
        with self.assertLogs('root', level='WARNING') as cm:
            bridge = ShokoBridge(mock_args, mock_config)
            bridge.run()
            self.assertIn("No TMDb Episode ID link found for a 'Normal' episode", cm.output[0])
            self.assertIn("Could not determine destination path or filename", cm.output[1])

        # --- Assert ---
        # Verify that the file was not processed or added to the DB
        file_manager.process_file_group.assert_not_called()
        db_manager.add_processed_file.assert_not_called()

        # Verify that the unmatched report was written to
        mock_open.assert_called_once_with('report.txt', 'w', encoding='utf-8')
        handle = mock_open()
        handle.write.assert_any_call("File: 'unmatched_episode.mkv' | ID: 123 | Reason: Could not determine destination path or filename. Skipping.\n")

    @patch('shokobridge.bridge.TMDbClient')
    @patch('shokobridge.bridge.ShokoClient')
    @patch('shokobridge.bridge.FileManager')
    @patch('shokobridge.bridge.DatabaseManager')
    @patch('shokobridge.bridge.ShokoBridge._clean_filename', side_effect=lambda x: x)
    @patch('shokobridge.bridge.get_windows_host_ip', return_value='127.0.0.1')
    @patch('shokobridge.bridge.os.path.isdir', return_value=True)
    def test_run_extra_file_special(self, mock_isdir, mock_get_ip, mock_clean_filename,
                                     mock_db_manager, mock_file_manager,
                                     mock_shoko_client, mock_tmdb_client):
        """
        Test a run with a file identified as a 'Special' extra.
        """
        # --- Arrange ---
        mock_args = MagicMock()
        mock_args.cleanup = False
        mock_args.dry_run = False
        mock_args.debug = False

        mock_config = {
            'directories': { 'source_root': '/source', 'destination': '/dest/shows' },
            'shoko': {'url': 'http://test.host:8111', 'api_key': 'test_key'},
            'tmdb': {'api_key': 'test_key'},
            'path_mappings': [],
            'options': { 'title_similarity_threshold': 0.85, 'link_type': 'symlink', 'use_relative_symlinks': False },
            'paths': { 'db': 'test.db', 'cache': 'cache.json', 'unmatched_report': 'report.txt' }
        }

        db_manager = mock_db_manager.return_value
        file_manager = mock_file_manager.return_value
        shoko_client = mock_shoko_client.return_value
        tmdb_client = mock_tmdb_client.return_value

        db_manager.get_processed_file_ids.return_value = set()
        shoko_client.get_all_file_ids.return_value = [123]
        shoko_client.check_connection.return_value = True

        # Mock API responses for a file that is a SPECIAL
        shoko_client.get_file_details.return_value = {
            'Locations': [{'RelativePath': 'series/special.mkv'}],
            'SeriesIDs': [{'SeriesID': {'TMDB': {'Show': [999]}}, 'EpisodeIDs': [{'ID': 456}]}]
        }
        # No TMDb episode ID, but AniDB type is 'Special'
        shoko_client.get_episode_details.return_value = { 'Name': 'My Awesome Special', 'AniDB': {'Type': 'Special'}, 'IDs': {'TMDB': {}} }
        tmdb_client.get_series_details.return_value = { 'name': 'Series Title', 'first_air_date': '2023-01-01', 'seasons': [] }
        file_manager.process_file_group.return_value = True

        # --- Act ---
        bridge = ShokoBridge(mock_args, mock_config)
        bridge.run()

        # --- Assert ---
        # Verify the path construction for an extra placed in the 'Featurettes' folder
        expected_dest_path = '/dest/shows/Series Title (2023)/Featurettes/My Awesome Special.mkv'
        file_manager.process_file_group.assert_called_once_with('/source/series/special.mkv', expected_dest_path, ANY)
        db_manager.add_processed_file.assert_called_once_with(123, expected_dest_path)

    @patch('shokobridge.bridge.TMDbClient')
    @patch('shokobridge.bridge.ShokoClient')
    @patch('shokobridge.bridge.FileManager')
    @patch('shokobridge.bridge.DatabaseManager')
    @patch('shokobridge.bridge.get_windows_host_ip', return_value='127.0.0.1')
    @patch('shokobridge.bridge.os.path.isdir', return_value=True)
    def test_run_cleanup_dry_run(self, mock_isdir, mock_get_ip,
                                 mock_db_manager, mock_file_manager,
                                 mock_shoko_client, mock_tmdb_client):
        """
        Test a cleanup run in dry-run mode to ensure no destructive actions are taken.
        """
        # --- Arrange ---
        mock_args = MagicMock()
        mock_args.cleanup = True
        mock_args.dry_run = True
        mock_args.debug = False

        mock_config = {
            'directories': {
                'source_root': '/source',
                'destination': '/dest/shows',
                'destination_movies': '/dest/movies'
            },
            'shoko': {'url': 'http://test.host:8111', 'api_key': 'test_key'},
            'tmdb': {'api_key': 'test_key'},
            'path_mappings': [],
            'options': { 'link_type': 'symlink', 'use_relative_symlinks': False },
            'paths': { 'db': 'test.db', 'cache': 'cache.json', 'unmatched_report': 'report.txt' }
        }

        db_manager = mock_db_manager.return_value
        file_manager = mock_file_manager.return_value
        shoko_client = mock_shoko_client.return_value

        shoko_client.get_all_file_ids.return_value = []
        db_manager.get_stale_entries.return_value = [
            {'shoko_file_id': 999, 'destination_path': '/dest/shows/Stale Show/S01/stale.mkv'}
        ]
        shoko_client.check_connection.return_value = True

        # --- Act & Assert Logs ---
        with self.assertLogs('root', level='WARNING') as cm:
            bridge = ShokoBridge(mock_args, mock_config)
            bridge.run()
            self.assertIn("DRY RUN MODE ENABLED: No files or database entries will be deleted.", cm.output[0])

        # --- Assert ---
        # Verify that NO destructive actions were taken due to dry_run=True
        file_manager.cleanup_stale_files.assert_not_called()
        db_manager.remove_stale_entry.assert_not_called()
        file_manager.cleanup_empty_dirs.assert_not_called()

    @patch('shokobridge.bridge.TMDbClient')
    @patch('shokobridge.bridge.ShokoClient')
    @patch('shokobridge.bridge.FileManager')
    @patch('shokobridge.bridge.DatabaseManager')
    @patch('shokobridge.bridge.ShokoBridge._clean_filename', side_effect=lambda x: x)
    @patch('shokobridge.bridge.get_windows_host_ip', return_value='127.0.0.1')
    @patch('shokobridge.bridge.os.path.isdir', return_value=True)
    def test_run_add_update_dry_run(self, mock_isdir, mock_get_ip, mock_clean_filename,
                                    mock_db_manager, mock_file_manager,
                                    mock_shoko_client, mock_tmdb_client):
        """
        Test an add/update run in dry-run mode to ensure no DB changes are made.
        """
        # --- Arrange ---
        mock_args = MagicMock()
        mock_args.cleanup = False
        mock_args.dry_run = True # Enable dry run
        mock_args.debug = False

        mock_config = {
            'directories': { 'source_root': '/source', 'destination': '/dest/shows' },
            'shoko': {'url': 'http://test.host:8111', 'api_key': 'test_key'},
            'tmdb': {'api_key': 'test_key'},
            'path_mappings': [],
            'options': { 'title_similarity_threshold': 0.85, 'link_type': 'symlink', 'use_relative_symlinks': False },
            'paths': { 'db': 'test.db', 'cache': 'cache.json', 'unmatched_report': 'report.txt' }
        }

        db_manager = mock_db_manager.return_value
        file_manager = mock_file_manager.return_value
        shoko_client = mock_shoko_client.return_value
        tmdb_client = mock_tmdb_client.return_value

        db_manager.get_processed_file_ids.return_value = set()
        shoko_client.get_all_file_ids.return_value = [123]
        shoko_client.check_connection.return_value = True

        # Mock API responses for a single TV show file
        shoko_client.get_file_details.return_value = { 'Locations': [{'RelativePath': 'series/episode.mkv'}], 'SeriesIDs': [{'SeriesID': {'TMDB': {'Show': [999]}}, 'EpisodeIDs': [{'ID': 456}]}] }
        shoko_client.get_episode_details.return_value = { 'Name': 'Episode Title', 'AniDB': {'Type': 'Normal'}, 'IDs': {'TMDB': {'Episode': [789]}}, 'TMDB': {'Episodes': [{'ID': 789, 'Title': 'Episode Title', 'SeasonNumber': 1, 'EpisodeNumber': 1}]} }
        tmdb_client.get_series_details.return_value = { 'name': 'Series Title', 'first_air_date': '2023-01-01' }

        # --- Act & Assert Logs ---
        with self.assertLogs('root', level='WARNING') as cm:
            bridge = ShokoBridge(mock_args, mock_config)
            bridge.run()
            self.assertIn("DRY RUN MODE ENABLED: No changes will be made", cm.output[0])

        # --- Assert ---
        # Verify that file processing logic was called (FileManager handles the dry run logging)
        file_manager.process_file_group.assert_called_once()
        # Verify that NO database write occurred due to dry_run=True
        db_manager.add_processed_file.assert_not_called()

    @patch('shokobridge.bridge.TMDbClient')
    @patch('shokobridge.bridge.ShokoClient')
    @patch('shokobridge.bridge.FileManager')
    @patch('shokobridge.bridge.DatabaseManager')
    @patch('shokobridge.bridge.ShokoBridge._clean_filename', side_effect=lambda x: x)
    @patch('shokobridge.bridge.get_windows_host_ip', return_value='127.0.0.1')
    @patch('shokobridge.bridge.os.path.isdir', return_value=True)
    def test_run_extra_file_trailer(self, mock_isdir, mock_get_ip, mock_clean_filename,
                                     mock_db_manager, mock_file_manager,
                                     mock_shoko_client, mock_tmdb_client):
        """
        Test a run with a file identified as a 'Trailer' extra.
        """
        # --- Arrange ---
        mock_args = MagicMock()
        mock_args.cleanup = False
        mock_args.dry_run = False
        mock_args.debug = False

        mock_config = {
            'directories': { 'source_root': '/source', 'destination': '/dest/shows' },
            'shoko': {'url': 'http://test.host:8111', 'api_key': 'test_key'},
            'tmdb': {'api_key': 'test_key'},
            'path_mappings': [],
            'options': { 'title_similarity_threshold': 0.85, 'link_type': 'symlink', 'use_relative_symlinks': False },
            'paths': { 'db': 'test.db', 'cache': 'cache.json', 'unmatched_report': 'report.txt' }
        }

        db_manager = mock_db_manager.return_value
        file_manager = mock_file_manager.return_value
        shoko_client = mock_shoko_client.return_value
        tmdb_client = mock_tmdb_client.return_value

        db_manager.get_processed_file_ids.return_value = set()
        shoko_client.get_all_file_ids.return_value = [123]
        shoko_client.check_connection.return_value = True

        # Mock API responses for a file that is a TRAILER
        shoko_client.get_file_details.return_value = { 'Locations': [{'RelativePath': 'series/trailer.mkv'}], 'SeriesIDs': [{'SeriesID': {'TMDB': {'Show': [999]}}, 'EpisodeIDs': [{'ID': 456}]}] }
        shoko_client.get_episode_details.return_value = { 'Name': 'Awesome Trailer', 'AniDB': {'Type': 'Trailer'}, 'IDs': {'TMDB': {}} }
        tmdb_client.get_series_details.return_value = { 'name': 'Series Title', 'first_air_date': '2023-01-01', 'seasons': [] }
        file_manager.process_file_group.return_value = True

        # --- Act ---
        bridge = ShokoBridge(mock_args, mock_config)
        bridge.run()

        # --- Assert ---
        # Verify the path construction for an extra placed in the 'Trailers' folder
        expected_dest_path = '/dest/shows/Series Title (2023)/Trailers/Awesome Trailer.mkv'
        file_manager.process_file_group.assert_called_once_with('/source/series/trailer.mkv', expected_dest_path, ANY)
        db_manager.add_processed_file.assert_called_once_with(123, expected_dest_path)

    @patch('shokobridge.bridge.TMDbClient')
    @patch('shokobridge.bridge.ShokoClient')
    @patch('shokobridge.bridge.FileManager')
    @patch('shokobridge.bridge.DatabaseManager')
    @patch('shokobridge.bridge.get_windows_host_ip', return_value='127.0.0.1')
    @patch('shokobridge.bridge.os.path.isdir', return_value=True)
    def test_run_skip_processed_file(self, mock_isdir, mock_get_ip,
                                     mock_db_manager, mock_file_manager,
                                     mock_shoko_client, mock_tmdb_client):
        """
        Test a run where a file is already in the database and should be skipped.
        """
        # --- Arrange ---
        mock_args = MagicMock()
        mock_args.cleanup = False
        mock_args.dry_run = False
        mock_args.debug = False

        mock_config = {
            'directories': { 'source_root': '/source', 'destination': '/dest/shows' },
            'shoko': {'url': 'http://test.host:8111', 'api_key': 'test_key'},
            'tmdb': {'api_key': 'test_key'},
            'path_mappings': [],
            'options': { 'title_similarity_threshold': 0.85, 'link_type': 'symlink', 'use_relative_symlinks': False },
            'paths': { 'db': 'test.db', 'cache': 'cache.json', 'unmatched_report': 'report.txt' }
        }

        db_manager = mock_db_manager.return_value
        file_manager = mock_file_manager.return_value
        shoko_client = mock_shoko_client.return_value

        # Simulate the file ID is already in the database
        shoko_client.get_all_file_ids.return_value = [123]
        db_manager.get_processed_file_ids.return_value = {123}
        shoko_client.check_connection.return_value = True

        # --- Act ---
        bridge = ShokoBridge(mock_args, mock_config)
        bridge.run()

        # --- Assert ---
        # Verify that no processing calls were made for the file
        shoko_client.get_file_details.assert_not_called()
        file_manager.process_file_group.assert_not_called()
        db_manager.add_processed_file.assert_not_called()

    @patch('shokobridge.bridge.open', new_callable=unittest.mock.mock_open)
    @patch('shokobridge.bridge.TMDbClient')
    @patch('shokobridge.bridge.ShokoClient')
    @patch('shokobridge.bridge.FileManager')
    @patch('shokobridge.bridge.DatabaseManager')
    @patch('shokobridge.bridge.get_windows_host_ip', return_value='127.0.0.1')
    @patch('shokobridge.bridge.os.path.isdir', return_value=True)
    def test_run_file_with_no_series(self, mock_isdir, mock_get_ip,
                                     mock_db_manager, mock_file_manager,
                                     mock_shoko_client, mock_tmdb_client, mock_open):
        """
        Test a run where a file is not linked to any series in Shoko.
        """
        # --- Arrange ---
        mock_args = MagicMock()
        mock_args.cleanup = False
        mock_args.dry_run = False
        mock_args.debug = False

        mock_config = {
            'directories': { 'source_root': '/source', 'destination': '/dest/shows' },
            'shoko': {'url': 'http://test.host:8111', 'api_key': 'test_key'},
            'tmdb': {'api_key': 'test_key'},
            'path_mappings': [],
            'options': { 'title_similarity_threshold': 0.85, 'link_type': 'symlink', 'use_relative_symlinks': False },
            'paths': { 'db': 'test.db', 'cache': 'cache.json', 'unmatched_report': 'report.txt' }
        }

        db_manager = mock_db_manager.return_value
        file_manager = mock_file_manager.return_value
        shoko_client = mock_shoko_client.return_value

        db_manager.get_processed_file_ids.return_value = set()
        shoko_client.get_all_file_ids.return_value = [123]
        shoko_client.check_connection.return_value = True
        shoko_client.get_file_details.return_value = { 'Locations': [{'RelativePath': 'unlinked/file.mkv'}], 'SeriesIDs': [] }

        # --- Act & Assert Logs ---
        with self.assertLogs('root', level='WARNING') as cm:
            bridge = ShokoBridge(mock_args, mock_config)
            bridge.run()
            self.assertIn("File is not linked to any series in Shoko. Skipping.", cm.output[0])

        # --- Assert ---
        shoko_client.get_episode_details.assert_not_called()
        file_manager.process_file_group.assert_not_called()
        handle = mock_open()
        handle.write.assert_any_call("File: 'file.mkv' | ID: 123 | Reason: File is not linked to any series in Shoko. Skipping.\n")

    @patch('shokobridge.bridge.open', new_callable=unittest.mock.mock_open)
    @patch('shokobridge.bridge.TMDbClient')
    @patch('shokobridge.bridge.ShokoClient')
    @patch('shokobridge.bridge.FileManager')
    @patch('shokobridge.bridge.DatabaseManager')
    @patch('shokobridge.bridge.get_windows_host_ip', return_value='127.0.0.1')
    @patch('shokobridge.bridge.os.path.isdir', return_value=True)
    def test_run_file_with_no_episodes(self, mock_isdir, mock_get_ip,
                                       mock_db_manager, mock_file_manager,
                                       mock_shoko_client, mock_tmdb_client, mock_open):
        """
        Test a run where a file is linked to a series but has no episode IDs.
        """
        # --- Arrange ---
        mock_args = MagicMock()
        mock_args.cleanup = False
        mock_args.dry_run = False
        mock_args.debug = False

        mock_config = {
            'directories': { 'source_root': '/source', 'destination': '/dest/shows' },
            'shoko': {'url': 'http://test.host:8111', 'api_key': 'test_key'},
            'tmdb': {'api_key': 'test_key'},
            'path_mappings': [],
            'options': { 'title_similarity_threshold': 0.85, 'link_type': 'symlink', 'use_relative_symlinks': False },
            'paths': { 'db': 'test.db', 'cache': 'cache.json', 'unmatched_report': 'report.txt' }
        }

        db_manager = mock_db_manager.return_value
        shoko_client = mock_shoko_client.return_value

        db_manager.get_processed_file_ids.return_value = set()
        shoko_client.get_all_file_ids.return_value = [123]
        shoko_client.check_connection.return_value = True
        shoko_client.get_file_details.return_value = { 'Locations': [{'RelativePath': 'series/no_ep_link.mkv'}], 'SeriesIDs': [{'EpisodeIDs': []}] }

        # --- Act & Assert Logs ---
        with self.assertLogs('root', level='WARNING') as cm:
            bridge = ShokoBridge(mock_args, mock_config)
            bridge.run()
            self.assertIn("File is not linked to any episodes in Shoko. Skipping.", cm.output[0])

        # --- Assert ---
        handle = mock_open()
        handle.write.assert_any_call("File: 'no_ep_link.mkv' | ID: 123 | Reason: File is not linked to any episodes in Shoko. Skipping.\n")

    @patch('shokobridge.bridge.open', new_callable=unittest.mock.mock_open)
    @patch('shokobridge.bridge.TMDbClient')
    @patch('shokobridge.bridge.ShokoClient')
    @patch('shokobridge.bridge.FileManager')
    @patch('shokobridge.bridge.DatabaseManager')
    @patch('shokobridge.bridge.get_windows_host_ip', return_value='127.0.0.1')
    @patch('shokobridge.bridge.os.path.isdir', return_value=True)
    def test_run_file_with_no_tmdb_series_id(self, mock_isdir, mock_get_ip,
                                             mock_db_manager, mock_file_manager,
                                             mock_shoko_client, mock_tmdb_client, mock_open):
        """
        Test a run where a file has a series link but no TMDb Show ID.
        """
        # --- Arrange ---
        mock_args = MagicMock()
        mock_args.cleanup = False
        mock_args.dry_run = False
        mock_args.debug = False

        mock_config = {
            'directories': { 'source_root': '/source', 'destination': '/dest/shows' },
            'shoko': {'url': 'http://test.host:8111', 'api_key': 'test_key'},
            'tmdb': {'api_key': 'test_key'},
            'path_mappings': [],
            'options': { 'title_similarity_threshold': 0.85, 'link_type': 'symlink', 'use_relative_symlinks': False },
            'paths': { 'db': 'test.db', 'cache': 'cache.json', 'unmatched_report': 'report.txt' }
        }

        db_manager = mock_db_manager.return_value
        shoko_client = mock_shoko_client.return_value
        file_manager = mock_file_manager.return_value

        db_manager.get_processed_file_ids.return_value = set()
        shoko_client.get_all_file_ids.return_value = [123]
        shoko_client.check_connection.return_value = True
        shoko_client.get_file_details.return_value = { 'Locations': [{'RelativePath': 'series/no_tmdb_id.mkv'}], 'SeriesIDs': [{'SeriesID': {'TMDB': {}}, 'EpisodeIDs': [{'ID': 456}]}] }
        shoko_client.get_episode_details.return_value = { 'Name': 'Some Episode', 'AniDB': {'Type': 'Normal'}, 'IDs': {'TMDB': {}} }

        # --- Act & Assert Logs ---
        with self.assertLogs('root', level='WARNING') as cm:
            bridge = ShokoBridge(mock_args, mock_config)
            bridge.run()
            self.assertIn("Could not find a TMDb Show ID link in Shoko's cross-reference data", cm.output[0])
            self.assertIn("Could not determine destination path or filename", cm.output[1])

        # --- Assert ---
        file_manager.process_file_group.assert_not_called()
        handle = mock_open()
        handle.write.assert_any_call("File: 'no_tmdb_id.mkv' | ID: 123 | Reason: Could not determine destination path or filename. Skipping.\n")

    @patch('shokobridge.bridge.TMDbClient')
    @patch('shokobridge.bridge.ShokoClient')
    @patch('shokobridge.bridge.FileManager')
    @patch('shokobridge.bridge.DatabaseManager')
    @patch('shokobridge.bridge.ShokoBridge._clean_filename', side_effect=lambda x: x)
    @patch('shokobridge.bridge.get_windows_host_ip', return_value='127.0.0.1')
    @patch('shokobridge.bridge.os.path.isdir', return_value=True)
    def test_run_file_with_no_tmdb_episode_id_fallback_success(self, mock_isdir, mock_get_ip, mock_clean_filename,
                                                               mock_db_manager, mock_file_manager,
                                                               mock_shoko_client, mock_tmdb_client):
        """
        Test a run where an episode has no TMDb ID, but successfully matches by title.
        """
        # --- Arrange ---
        mock_args = MagicMock()
        mock_args.cleanup = False
        mock_args.dry_run = False
        mock_args.debug = False

        mock_config = {
            'directories': { 'source_root': '/source', 'destination': '/dest/shows' },
            'shoko': {'url': 'http://test.host:8111', 'api_key': 'test_key'},
            'tmdb': {'api_key': 'test_key'},
            'path_mappings': [],
            'options': { 'title_similarity_threshold': 0.85, 'link_type': 'symlink', 'use_relative_symlinks': False },
            'paths': { 'db': 'test.db', 'cache': 'cache.json', 'unmatched_report': 'report.txt' }
        }

        db_manager = mock_db_manager.return_value
        file_manager = mock_file_manager.return_value
        shoko_client = mock_shoko_client.return_value
        tmdb_client = mock_tmdb_client.return_value

        db_manager.get_processed_file_ids.return_value = set()
        shoko_client.get_all_file_ids.return_value = [123]
        shoko_client.check_connection.return_value = True

        # Mock API responses for a file with no TMDb Episode ID
        shoko_client.get_file_details.return_value = { 'Locations': [{'RelativePath': 'series/fallback_ep.mkv'}], 'SeriesIDs': [{'SeriesID': {'TMDB': {'Show': [999]}}, 'EpisodeIDs': [{'ID': 456}]}] }
        shoko_client.get_episode_details.return_value = { 'Name': 'The Great Fallback Episode', 'AniDB': {'Type': 'Normal'}, 'IDs': {'TMDB': {}} }
        tmdb_client.get_series_details.return_value = { 'name': 'Series Title', 'first_air_date': '2023-01-01', 'seasons': [{'season_number': 1, 'name': 'Season 1'}] }
        tmdb_client.get_season_details.return_value = [ {'id': 789, 'name': 'The Great Fallback Episode', 'season_number': 1, 'episode_number': 5} ]
        file_manager.process_file_group.return_value = True

        # --- Act & Assert Logs ---
        with self.assertLogs('root', level='INFO') as cm:
            bridge = ShokoBridge(mock_args, mock_config)
            bridge.run()
            # cm.output[0] is "--- Starting ADD/UPDATE Run ---"
            # cm.output[1] is "Found 1 new files to process."
            self.assertIn("No TMDb Episode ID link found for a 'Normal' episode. Attempting fallback match by title...", cm.output[2])
            self.assertIn("SUCCESS (Fallback Match): Matched to S1E5 with similarity 1.00!", cm.output[3])

        # --- Assert ---
        tmdb_client.get_season_details.assert_called_once_with(999, 1)
        expected_dest_path = '/dest/shows/Series Title (2023)/Season 01/Series Title (2023) - S01E05 - The Great Fallback Episode.mkv'
        file_manager.process_file_group.assert_called_once_with('/source/series/fallback_ep.mkv', expected_dest_path, ANY)
        db_manager.add_processed_file.assert_called_once_with(123, expected_dest_path)

    @patch('shokobridge.bridge.open', new_callable=unittest.mock.mock_open)
    @patch('shokobridge.bridge.TMDbClient')
    @patch('shokobridge.bridge.ShokoClient')
    @patch('shokobridge.bridge.FileManager')
    @patch('shokobridge.bridge.DatabaseManager')
    @patch('shokobridge.bridge.get_windows_host_ip', return_value='127.0.0.1')
    @patch('shokobridge.bridge.os.path.isdir', return_value=True)
    def test_run_file_with_no_tmdb_episode_id_fallback_fail(self, mock_isdir, mock_get_ip,
                                                            mock_db_manager, mock_file_manager,
                                                            mock_shoko_client, mock_tmdb_client, mock_open):
        """
        Test a run where an episode has no TMDb ID and the title match fallback fails.
        """
        # --- Arrange ---
        mock_args = MagicMock()
        mock_args.cleanup = False
        mock_args.dry_run = False
        mock_args.debug = False

        mock_config = {
            'directories': { 'source_root': '/source', 'destination': '/dest/shows' },
            'shoko': {'url': 'http://test.host:8111', 'api_key': 'test_key'},
            'tmdb': {'api_key': 'test_key'},
            'path_mappings': [],
            'options': { 'title_similarity_threshold': 0.85, 'link_type': 'symlink', 'use_relative_symlinks': False },
            'paths': { 'db': 'test.db', 'cache': 'cache.json', 'unmatched_report': 'report.txt' }
        }

        db_manager = mock_db_manager.return_value
        file_manager = mock_file_manager.return_value
        shoko_client = mock_shoko_client.return_value
        tmdb_client = mock_tmdb_client.return_value

        db_manager.get_processed_file_ids.return_value = set()
        shoko_client.get_all_file_ids.return_value = [123]
        shoko_client.check_connection.return_value = True

        # Mock API responses for a file with no TMDb Episode ID and a non-matching title
        shoko_client.get_file_details.return_value = { 'Locations': [{'RelativePath': 'series/fallback_fail.mkv'}], 'SeriesIDs': [{'SeriesID': {'TMDB': {'Show': [999]}}, 'EpisodeIDs': [{'ID': 456}]}] }
        shoko_client.get_episode_details.return_value = { 'Name': 'The Great Fallback Episode', 'AniDB': {'Type': 'Normal'}, 'IDs': {'TMDB': {}} }
        tmdb_client.get_series_details.return_value = { 'name': 'Series Title', 'first_air_date': '2023-01-01', 'seasons': [{'season_number': 1, 'name': 'Season 1'}] }
        # The TMDb title is completely different, so similarity will be low
        tmdb_client.get_season_details.return_value = [ {'id': 789, 'name': 'A Completely Different Title', 'season_number': 1, 'episode_number': 5} ]

        # --- Act & Assert Logs ---
        with self.assertLogs('root', level='WARNING') as cm:
            bridge = ShokoBridge(mock_args, mock_config)
            bridge.run()
            self.assertIn("No TMDb Episode ID link found for a 'Normal' episode. Attempting fallback match by title...", cm.output[0])
            self.assertIn("Could not determine destination path or filename", cm.output[1])

        # --- Assert ---
        file_manager.process_file_group.assert_not_called()
        db_manager.add_processed_file.assert_not_called()
        handle = mock_open()
        handle.write.assert_any_call("File: 'fallback_fail.mkv' | ID: 123 | Reason: Could not determine destination path or filename. Skipping.\n")

    @patch('shokobridge.bridge.TMDbClient')
    @patch('shokobridge.bridge.ShokoClient')
    @patch('shokobridge.bridge.FileManager')
    @patch('shokobridge.bridge.DatabaseManager')
    @patch('shokobridge.bridge.ShokoBridge._clean_filename', side_effect=lambda x: x)
    @patch('shokobridge.bridge.get_windows_host_ip', return_value='127.0.0.1')
    @patch('shokobridge.bridge.os.path.isdir', return_value=True)
    def test_run_movie_file_tmdb_api_fallback(self, mock_isdir, mock_get_ip, mock_clean_filename,
                                              mock_db_manager, mock_file_manager,
                                              mock_shoko_client, mock_tmdb_client):
        """
        Test a run where a movie file forces a fallback to the TMDb API.
        """
        # --- Arrange ---
        mock_args = MagicMock()
        mock_args.cleanup = False
        mock_args.dry_run = False
        mock_args.debug = False

        mock_config = {
            'directories': { 'source_root': '/source', 'destination': '/dest/shows', 'destination_movies': '/dest/movies' },
            'shoko': {'url': 'http://test.host:8111', 'api_key': 'test_key'},
            'tmdb': {'api_key': 'test_key'},
            'path_mappings': [],
            'options': { 'title_similarity_threshold': 0.85, 'link_type': 'symlink', 'use_relative_symlinks': False },
            'paths': { 'db': 'test.db', 'cache': 'cache.json', 'unmatched_report': 'report.txt' }
        }

        db_manager = mock_db_manager.return_value
        file_manager = mock_file_manager.return_value
        shoko_client = mock_shoko_client.return_value
        tmdb_client = mock_tmdb_client.return_value

        db_manager.get_processed_file_ids.return_value = set()
        shoko_client.get_all_file_ids.return_value = [123]
        shoko_client.check_connection.return_value = True

        # Mock Shoko API response *without* full movie data, forcing a TMDb call
        shoko_client.get_file_details.return_value = { 'Locations': [{'RelativePath': 'movies/movie_fallback.mkv'}], 'SeriesIDs': [{'EpisodeIDs': [{'ID': 456}]}] }
        shoko_client.get_episode_details.return_value = { 'Name': 'Movie Title', 'AniDB': {'Type': 'Movie'}, 'IDs': {'TMDB': {'Movie': [98765]}}, 'TMDB': {} }
        tmdb_client.get_movie_details.return_value = { 'title': 'Movie Title from API', 'release_date': '2025-01-01' }
        file_manager.process_file_group.return_value = True

        # --- Act & Assert Logs ---
        with self.assertLogs('root', level='INFO') as cm:
            bridge = ShokoBridge(mock_args, mock_config)
            bridge.run()
            self.assertIn("Shoko did not provide full data. Querying TMDb API as a fallback...", cm.output[3])

        # --- Assert ---
        tmdb_client.get_movie_details.assert_called_once_with(98765)
        expected_dest_path = '/dest/movies/Movie Title from API (2025)/Movie Title from API (2025).mkv'
        file_manager.process_file_group.assert_called_once_with('/source/movies/movie_fallback.mkv', expected_dest_path, ANY)
        db_manager.add_processed_file.assert_called_once_with(123, expected_dest_path)

    @patch('shokobridge.bridge.TMDbClient')
    @patch('shokobridge.bridge.ShokoClient')
    @patch('shokobridge.bridge.FileManager')
    @patch('shokobridge.bridge.DatabaseManager')
    @patch('shokobridge.bridge.ShokoBridge._clean_filename', side_effect=lambda x: x)
    @patch('shokobridge.bridge.get_windows_host_ip', return_value='127.0.0.1')
    @patch('shokobridge.bridge.os.path.isdir', return_value=True)
    def test_run_tv_episode_tmdb_api_fallback(self, mock_isdir, mock_get_ip, mock_clean_filename,
                                              mock_db_manager, mock_file_manager,
                                              mock_shoko_client, mock_tmdb_client):
        """
        Test a run where a TV episode forces a fallback to the TMDb API for season details.
        """
        # --- Arrange ---
        mock_args = MagicMock()
        mock_args.cleanup = False
        mock_args.dry_run = False
        mock_args.debug = False

        mock_config = {
            'directories': { 'source_root': '/source', 'destination': '/dest/shows' },
            'shoko': {'url': 'http://test.host:8111', 'api_key': 'test_key'},
            'tmdb': {'api_key': 'test_key'},
            'path_mappings': [],
            'options': { 'title_similarity_threshold': 0.85, 'link_type': 'symlink', 'use_relative_symlinks': False },
            'paths': { 'db': 'test.db', 'cache': 'cache.json', 'unmatched_report': 'report.txt' }
        }

        db_manager = mock_db_manager.return_value
        file_manager = mock_file_manager.return_value
        shoko_client = mock_shoko_client.return_value
        tmdb_client = mock_tmdb_client.return_value

        db_manager.get_processed_file_ids.return_value = set()
        shoko_client.get_all_file_ids.return_value = [123]
        shoko_client.check_connection.return_value = True

        # Mock Shoko API response with a TMDb Episode ID but no detailed episode data
        shoko_client.get_file_details.return_value = { 'Locations': [{'RelativePath': 'series/tv_fallback.mkv'}], 'SeriesIDs': [{'SeriesID': {'TMDB': {'Show': [999]}}, 'EpisodeIDs': [{'ID': 456}]}] }
        shoko_client.get_episode_details.return_value = { 'Name': 'Some Episode', 'AniDB': {'Type': 'Normal'}, 'IDs': {'TMDB': {'Episode': [789]}}, 'TMDB': {} }
        tmdb_client.get_series_details.return_value = { 'name': 'Series Title', 'first_air_date': '2023-01-01', 'seasons': [{'season_number': 1, 'name': 'Season 1'}] }
        tmdb_client.get_season_details.return_value = [ {'id': 789, 'name': 'Episode from API', 'season_number': 1, 'episode_number': 5} ]
        file_manager.process_file_group.return_value = True

        # --- Act ---
        bridge = ShokoBridge(mock_args, mock_config)
        bridge.run()

        # --- Assert ---
        tmdb_client.get_series_details.assert_called_once_with(999)
        tmdb_client.get_season_details.assert_called_once_with(999, 1)
        expected_dest_path = '/dest/shows/Series Title (2023)/Season 01/Series Title (2023) - S01E05 - Episode from API.mkv'
        file_manager.process_file_group.assert_called_once_with('/source/series/tv_fallback.mkv', expected_dest_path, ANY)
        db_manager.add_processed_file.assert_called_once_with(123, expected_dest_path)

    @patch('shokobridge.bridge.TMDbClient')
    @patch('shokobridge.bridge.ShokoClient')
    @patch('shokobridge.bridge.FileManager')
    @patch('shokobridge.bridge.DatabaseManager')
    @patch('shokobridge.bridge.ShokoBridge._clean_filename', side_effect=lambda x: x)
    @patch('shokobridge.bridge.get_windows_host_ip', return_value='127.0.0.1')
    @patch('shokobridge.bridge.os.path.isdir', return_value=True)
    def test_run_with_supplemental_files(self, mock_isdir, mock_get_ip, mock_clean_filename,
                                         mock_db_manager, mock_file_manager,
                                         mock_shoko_client, mock_tmdb_client):
        """
        Test that ShokoBridge correctly calls FileManager to process a media file
        and its associated supplemental files (e.g., .srt, .ass).
        """
        # --- Arrange ---
        mock_args = MagicMock()
        mock_args.cleanup = False
        mock_args.dry_run = False
        mock_args.debug = False

        mock_config = {
            'directories': { 'source_root': '/source', 'destination': '/dest/shows' },
            'shoko': {'url': 'http://test.host:8111', 'api_key': 'test_key'},
            'tmdb': {'api_key': 'test_key'},
            'path_mappings': [],
            'options': { 'title_similarity_threshold': 0.85, 'link_type': 'symlink', 'use_relative_symlinks': False },
            'paths': { 'db': 'test.db', 'cache': 'cache.json', 'unmatched_report': 'report.txt' }
        }

        db_manager = mock_db_manager.return_value
        file_manager = mock_file_manager.return_value
        shoko_client = mock_shoko_client.return_value
        tmdb_client = mock_tmdb_client.return_value

        db_manager.get_processed_file_ids.return_value = set()
        shoko_client.get_all_file_ids.return_value = [1499] # Using an ID from the log
        shoko_client.check_connection.return_value = True

        # Mock API responses for a One Piece episode
        shoko_client.get_file_details.return_value = { 'Locations': [{'RelativePath': 'One Piece/One Piece - 1107 [9A4CD29B].mkv'}], 'SeriesIDs': [{'SeriesID': {'TMDB': {'Show': [37854]}}, 'EpisodeIDs': [{'ID': 3645}]}] }
        shoko_client.get_episode_details.return_value = { 'Name': 'A Shudder! The Evil Hand Creeping Up on the Laboratory', 'AniDB': {'Type': 'Normal'}, 'IDs': {'TMDB': {'Episode': [5343000]}}, 'TMDB': {'Episodes': [{'ID': 5343000, 'Title': 'A Shudder! The Evil Hand Creeping Up on the Laboratory', 'SeasonNumber': 22, 'EpisodeNumber': 1107}]} }
        tmdb_client.get_series_details.return_value = { 'name': 'One Piece', 'first_air_date': '1999-10-20' }
        file_manager.process_file_group.return_value = True

        # --- Act ---
        bridge = ShokoBridge(mock_args, mock_config)
        bridge.run()

        # --- Assert ---
        # The core of this test is to ensure ShokoBridge passes the correct paths to FileManager.
        # FileManager is then responsible for finding and handling the supplemental files.
        expected_source_path = '/source/One Piece/One Piece - 1107 [9A4CD29B].mkv'
        expected_dest_path = '/dest/shows/One Piece (1999)/Season 22/One Piece (1999) - S22E1107 - A Shudder! The Evil Hand Creeping Up on the Laboratory.mkv'
        file_manager.process_file_group.assert_called_once_with(expected_source_path, expected_dest_path, ANY)
        db_manager.add_processed_file.assert_called_once_with(1499, expected_dest_path)

    @patch('shokobridge.bridge.TMDbClient')
    @patch('shokobridge.bridge.ShokoClient')
    @patch('shokobridge.bridge.FileManager')
    @patch('shokobridge.bridge.DatabaseManager')
    @patch('shokobridge.bridge.ShokoBridge._clean_filename', side_effect=lambda x: x)
    @patch('shokobridge.bridge.get_windows_host_ip', return_value='127.0.0.1')
    @patch('shokobridge.bridge.os.path.isdir', return_value=True)
    def test_run_movie_file_no_movie_destination(self, mock_isdir, mock_get_ip, mock_clean_filename,
                                                 mock_db_manager, mock_file_manager,
                                                 mock_shoko_client, mock_tmdb_client):
        """
        Test a movie is placed in the main destination folder when destination_movies is not set.
        """
        # --- Arrange ---
        mock_args = MagicMock()
        mock_args.cleanup = False
        mock_args.dry_run = False
        mock_args.debug = False

        # Mock config *without* a separate movie destination
        mock_config = {
            'directories': {
                'source_root': '/source',
                'destination': '/dest/media', # Using a generic name to make the test clear
            },
            'shoko': {'url': 'http://test.host:8111', 'api_key': 'test_key'},
            'tmdb': {'api_key': 'test_key'},
            'path_mappings': [],
            'options': { 'title_similarity_threshold': 0.85, 'link_type': 'symlink', 'use_relative_symlinks': False },
            'paths': { 'db': 'test.db', 'cache': 'cache.json', 'unmatched_report': 'report.txt' }
        }

        db_manager = mock_db_manager.return_value
        file_manager = mock_file_manager.return_value
        shoko_client = mock_shoko_client.return_value

        db_manager.get_processed_file_ids.return_value = set()
        shoko_client.get_all_file_ids.return_value = [123]
        shoko_client.check_connection.return_value = True

        # Mock API responses for a MOVIE
        shoko_client.get_file_details.return_value = { 'Locations': [{'RelativePath': 'movies/movie.mkv'}], 'SeriesIDs': [{'EpisodeIDs': [{'ID': 456}]}] }
        shoko_client.get_episode_details.return_value = { 'Name': 'Movie Title', 'AniDB': {'Type': 'Movie'}, 'IDs': {'TMDB': {'Movie': [98765]}}, 'TMDB': {'Movies': [{'ID': 98765, 'Title': 'Movie Title from TMDb', 'ReleasedAt': '2024-01-01'}]} }
        file_manager.process_file_group.return_value = True

        # --- Act ---
        bridge = ShokoBridge(mock_args, mock_config)
        bridge.run()

        # --- Assert ---
        # Verify the destination path is based on the main 'destination' directory
        expected_dest_path = '/dest/media/Movie Title from TMDb (2024)/Movie Title from TMDb (2024).mkv'
        file_manager.process_file_group.assert_called_once_with('/source/movies/movie.mkv', expected_dest_path, ANY)
        db_manager.add_processed_file.assert_called_once_with(123, expected_dest_path)

    @patch('shokobridge.bridge.TMDbClient')
    @patch('shokobridge.bridge.ShokoClient')
    @patch('shokobridge.bridge.FileManager')
    @patch('shokobridge.bridge.DatabaseManager')
    @patch('shokobridge.bridge.ShokoBridge._clean_filename', side_effect=lambda x: x)
    @patch('shokobridge.bridge.get_windows_host_ip', return_value='127.0.0.1')
    @patch('shokobridge.bridge.os.path.isdir', return_value=True)
    def test_run_extra_file_other(self, mock_isdir, mock_get_ip, mock_clean_filename,
                                  mock_db_manager, mock_file_manager,
                                  mock_shoko_client, mock_tmdb_client):
        """
        Test a run with a file identified as an 'Other' type extra.
        """
        # --- Arrange ---
        mock_args = MagicMock()
        mock_args.cleanup = False
        mock_args.dry_run = False
        mock_args.debug = False

        mock_config = {
            'directories': { 'source_root': '/source', 'destination': '/dest/shows' },
            'shoko': {'url': 'http://test.host:8111', 'api_key': 'test_key'},
            'tmdb': {'api_key': 'test_key'},
            'path_mappings': [],
            'options': { 'title_similarity_threshold': 0.85, 'link_type': 'symlink', 'use_relative_symlinks': False },
            'paths': { 'db': 'test.db', 'cache': 'cache.json', 'unmatched_report': 'report.txt' }
        }

        db_manager = mock_db_manager.return_value
        file_manager = mock_file_manager.return_value
        shoko_client = mock_shoko_client.return_value
        tmdb_client = mock_tmdb_client.return_value

        db_manager.get_processed_file_ids.return_value = set()
        shoko_client.get_all_file_ids.return_value = [123]
        shoko_client.check_connection.return_value = True

        shoko_client.get_file_details.return_value = { 'Locations': [{'RelativePath': 'series/other_extra.mkv'}], 'SeriesIDs': [{'SeriesID': {'TMDB': {'Show': [999]}}, 'EpisodeIDs': [{'ID': 456}]}] }
        shoko_client.get_episode_details.return_value = { 'Name': 'My Other Extra', 'AniDB': {'Type': 'Other'}, 'IDs': {'TMDB': {}} }
        tmdb_client.get_series_details.return_value = { 'name': 'Series Title', 'first_air_date': '2023-01-01', 'seasons': [] }
        file_manager.process_file_group.return_value = True

        # --- Act ---
        bridge = ShokoBridge(mock_args, mock_config)
        bridge.run()

        # --- Assert ---
        expected_dest_path = '/dest/shows/Series Title (2023)/Other/My Other Extra.mkv'
        file_manager.process_file_group.assert_called_once_with('/source/series/other_extra.mkv', expected_dest_path, ANY)
        db_manager.add_processed_file.assert_called_once_with(123, expected_dest_path)

    @patch('shokobridge.bridge.open', new_callable=unittest.mock.mock_open)
    @patch('shokobridge.bridge.TMDbClient')
    @patch('shokobridge.bridge.ShokoClient')
    @patch('shokobridge.bridge.FileManager')
    @patch('shokobridge.bridge.DatabaseManager')
    @patch('shokobridge.bridge.ShokoBridge._clean_filename', side_effect=lambda x: x)
    @patch('shokobridge.bridge.get_windows_host_ip', return_value='127.0.0.1')
    @patch('shokobridge.bridge.os.path.isdir', return_value=True)
    def test_run_shoko_api_error_graceful_handling(self, mock_isdir, mock_get_ip, mock_clean_filename,
                                                   mock_db_manager, mock_file_manager,
                                                   mock_shoko_client, mock_tmdb_client, mock_open):
        """
        Test that the script handles an unexpected Shoko API error gracefully and continues.
        """
        # --- Arrange ---
        mock_args = MagicMock()
        mock_args.cleanup = False
        mock_args.dry_run = False
        mock_args.debug = False

        mock_config = {
            'directories': { 'source_root': '/source', 'destination': '/dest/shows' },
            'shoko': {'url': 'http://test.host:8111', 'api_key': 'test_key'},
            'tmdb': {'api_key': 'test_key'},
            'path_mappings': [],
            'options': { 'title_similarity_threshold': 0.85, 'link_type': 'symlink', 'use_relative_symlinks': False },
            'paths': { 'db': 'test.db', 'cache': 'cache.json', 'unmatched_report': 'report.txt' }
        }

        db_manager = mock_db_manager.return_value
        file_manager = mock_file_manager.return_value
        shoko_client = mock_shoko_client.return_value
        tmdb_client = mock_tmdb_client.return_value

        db_manager.get_processed_file_ids.return_value = set()
        shoko_client.get_all_file_ids.return_value = [101, 102]
        shoko_client.check_connection.return_value = True

        shoko_client.get_file_details.side_effect = [ Exception("Shoko API is down!"), { 'Locations': [{'RelativePath': 'series/episode.mkv'}], 'SeriesIDs': [{'SeriesID': {'TMDB': {'Show': [999]}}, 'EpisodeIDs': [{'ID': 456}]}] } ]
        shoko_client.get_episode_details.return_value = { 'Name': 'Episode Title', 'AniDB': {'Type': 'Normal'}, 'IDs': {'TMDB': {'Episode': [789]}}, 'TMDB': {'Episodes': [{'ID': 789, 'Title': 'Episode Title', 'SeasonNumber': 1, 'EpisodeNumber': 1}]} }
        tmdb_client.get_series_details.return_value = { 'name': 'Series Title', 'first_air_date': '2023-01-01' }
        file_manager.process_file_group.return_value = True

        # --- Act & Assert Logs ---
        with self.assertLogs('root', level='ERROR') as cm:
            bridge = ShokoBridge(mock_args, mock_config)
            bridge.run()
            self.assertIn("An unexpected error occurred processing file ID 101: Shoko API is down!", cm.output[0])

        # --- Assert ---
        file_manager.process_file_group.assert_called_once()
        expected_dest_path = '/dest/shows/Series Title (2023)/Season 01/Series Title (2023) - S01E01 - Episode Title.mkv'
        db_manager.add_processed_file.assert_called_once_with(102, expected_dest_path)
        handle = mock_open()
        handle.write.assert_any_call("File ID: 101 | Reason: Unexpected script error - Shoko API is down!\n")

    @patch('shokobridge.bridge.open', new_callable=unittest.mock.mock_open)
    @patch('shokobridge.bridge.TMDbClient')
    @patch('shokobridge.bridge.ShokoClient')
    @patch('shokobridge.bridge.FileManager')
    @patch('shokobridge.bridge.DatabaseManager')
    @patch('shokobridge.bridge.ShokoBridge._clean_filename', side_effect=lambda x: x)
    @patch('shokobridge.bridge.get_windows_host_ip', return_value='127.0.0.1')
    @patch('shokobridge.bridge.os.path.isdir', return_value=True)
    def test_run_tmdb_api_error_graceful_handling(self, mock_isdir, mock_get_ip, mock_clean_filename,
                                                  mock_db_manager, mock_file_manager,
                                                  mock_shoko_client, mock_tmdb_client, mock_open):
        """
        Test that the script handles a TMDb API error gracefully and continues.
        """
        # --- Arrange ---
        mock_args = MagicMock()
        mock_args.cleanup = False
        mock_args.dry_run = False
        mock_args.debug = False

        mock_config = {
            'directories': { 'source_root': '/source', 'destination': '/dest/shows' },
            'shoko': {'url': 'http://test.host:8111', 'api_key': 'test_key'},
            'tmdb': {'api_key': 'test_key'},
            'path_mappings': [],
            'options': { 'title_similarity_threshold': 0.85, 'link_type': 'symlink', 'use_relative_symlinks': False },
            'paths': { 'db': 'test.db', 'cache': 'cache.json', 'unmatched_report': 'report.txt' }
        }

        db_manager = mock_db_manager.return_value
        file_manager = mock_file_manager.return_value
        shoko_client = mock_shoko_client.return_value
        tmdb_client = mock_tmdb_client.return_value

        db_manager.get_processed_file_ids.return_value = set()
        shoko_client.get_all_file_ids.return_value = [201, 202]
        shoko_client.check_connection.return_value = True

        shoko_client.get_file_details.side_effect = [ { 'Locations': [{'RelativePath': 'series/failed_ep.mkv'}], 'SeriesIDs': [{'SeriesID': {'TMDB': {'Show': [888]}}, 'EpisodeIDs': [{'ID': 456}]}] }, { 'Locations': [{'RelativePath': 'series/success_ep.mkv'}], 'SeriesIDs': [{'SeriesID': {'TMDB': {'Show': [999]}}, 'EpisodeIDs': [{'ID': 789}]}] } ]
        shoko_client.get_episode_details.side_effect = [ { 'Name': 'Failed Episode', 'AniDB': {'Type': 'Normal'}, 'IDs': {'TMDB': {}} }, { 'Name': 'Successful Episode', 'AniDB': {'Type': 'Normal'}, 'IDs': {'TMDB': {'Episode': [12345]}}, 'TMDB': {'Episodes': [{'ID': 12345, 'Title': 'Successful Episode', 'SeasonNumber': 1, 'EpisodeNumber': 2}]}} ]
        tmdb_client.get_series_details.side_effect = [ None, { 'name': 'Successful Series', 'first_air_date': '2024-01-01' } ]
        file_manager.process_file_group.return_value = True

        # --- Act & Assert Logs ---
        with self.assertLogs('root', level='WARNING') as cm:
            bridge = ShokoBridge(mock_args, mock_config)
            bridge.run()
            self.assertIn("Cannot process because TMDb series data could not be fetched for show ID 888.", cm.output[0])

        # --- Assert ---
        file_manager.process_file_group.assert_called_once()
        expected_dest_path = '/dest/shows/Successful Series (2024)/Season 01/Successful Series (2024) - S01E02 - Successful Episode.mkv'
        db_manager.add_processed_file.assert_called_once_with(202, expected_dest_path)
        handle = mock_open()
        handle.write.assert_any_call("File: 'failed_ep.mkv' | ID: 201 | Reason: Could not determine destination path or filename. Skipping.\n")