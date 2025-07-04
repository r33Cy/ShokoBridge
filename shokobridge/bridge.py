# shokobridge/bridge.py
import logging
import os
import re
import requests
from difflib import SequenceMatcher

from .clients.shoko import ShokoClient
from .clients.tmdb import TMDbClient
from .database import DatabaseManager
from .file_manager import FileManager
from .utils import get_windows_host_ip

class ShokoBridge:
    """The main application class for ShokoBridge."""

    def __init__(self, args, config):
        """
        Initializes the ShokoBridge application.

        :param args: The command-line arguments.
        :param config: The application configuration.
        """
        self.args = args
        self.config = config
        self.session = None
        self.shoko_client = None
        self.tmdb_client = None
        self.db_manager = None
        self.file_manager = None

    def run(self):
        """
        Runs the main application logic.
        Initializes components, runs the selected mode, and handles cleanup.
        """
        self.session = requests.Session()
        try:
            # --- Component Initialization ---
            source_root = self.config['directories']['source_root']
            if not os.path.isdir(source_root):
                logging.critical("Configuration Error: The 'source_root' directory does not exist or is not a directory: %s", source_root)
                return

            logging.debug("--- Configuration Summary ---")
            logging.debug("Mode: %s", "Cleanup" if self.args.cleanup else "Add/Update")
            logging.debug("Dry Run: %s", self.args.dry_run)
            logging.debug("Link Type: %s", self.config['options'].get('link_type', 'symlink'))
            logging.debug("Source Root: %s", source_root)
            logging.debug("Destination (Shows): %s", self.config['directories']['destination'])
            logging.debug("Destination (Movies): %s", self.config['directories'].get('destination_movies', 'Not Set'))

            self.db_manager = DatabaseManager(self.config['paths']['db'])
            self.db_manager.setup()

            self.file_manager = FileManager(self.config, self.args.dry_run)

            # Resolve WSL host IP if necessary
            shoko_url = self.config['shoko']['url']
            if 'windows.host' in shoko_url:
                host_ip = get_windows_host_ip()
                if host_ip:
                    self.config['shoko']['url'] = shoko_url.replace('windows.host', host_ip)
                else:
                    logging.critical("Could not resolve 'windows.host'. Please set the Shoko IP manually in the config. Exiting.")
                    return

            self.shoko_client = ShokoClient(self.config['shoko']['url'], self.config['shoko']['api_key'], self.session)
            self.tmdb_client = TMDbClient(self.config['tmdb']['api_key'], self.config['paths']['cache'], self.session)

            if not self.shoko_client.check_connection():
                logging.critical("Exiting due to failed connection check.")
                return

            # --- Mode Execution ---
            if self.args.cleanup:
                self._run_cleanup()
            else:
                self._run_add_new()

        finally:
            # --- Resource Cleanup ---
            if self.tmdb_client:
                self.tmdb_client.save_cache()
            if self.db_manager:
                self.db_manager.close_connection()
            if self.session:
                self.session.close()
            logging.info("Script finished.")

    def _run_add_new(self):
        """Handles the logic for adding/updating media files."""
        logging.info("--- Starting ADD/UPDATE Run ---")
        if self.args.dry_run:
            logging.warning("DRY RUN MODE ENABLED: No changes will be made to the filesystem or database.")

        dest_shows = self.config['directories']['destination']
        dest_movies = self.config['directories'].get('destination_movies') or dest_shows

        processed_file_ids = self.db_manager.get_processed_file_ids()
        all_shoko_file_ids = self.shoko_client.get_all_file_ids()

        files_to_process_ids = [fid for fid in all_shoko_file_ids if fid not in processed_file_ids]
        logging.info("Found %d new files to process.", len(files_to_process_ids))
        
        if not files_to_process_ids:
            logging.info("No new files to process. Library is up to date.")
            return

        unmatched_report = []
        dir_cache = {}

        for shoko_file_id in files_to_process_ids:
            try:
                logging.debug("\n--- Processing File ID: %d ---", shoko_file_id)
                file_data = self.shoko_client.get_file_details(shoko_file_id)
                if not file_data:
                    logging.warning("Could not get details for Shoko File ID %d. Skipping.", shoko_file_id)
                    unmatched_report.append(f"File ID: {shoko_file_id} | Reason: Failed to fetch file details from Shoko.")
                    continue

                original_filename = os.path.basename(file_data['Locations'][0]['RelativePath'])
                logging.debug("  File: '%s'", original_filename)
                
                series_id_data = file_data.get('SeriesIDs', [])
                if not series_id_data:
                    msg = "File is not linked to any series in Shoko. Skipping."
                    logging.warning("  %s", msg)
                    unmatched_report.append(f"File: '{original_filename}' | ID: {shoko_file_id} | Reason: {msg}")
                    continue
                
                episode_id_data = series_id_data[0].get('EpisodeIDs', [])
                if not episode_id_data:
                    msg = "File is not linked to any episodes in Shoko. Skipping."
                    logging.warning("  %s", msg)
                    unmatched_report.append(f"File: '{original_filename}' | ID: {shoko_file_id} | Reason: {msg}")
                    continue
                
                shoko_ep_id = episode_id_data[0].get('ID')
                if not shoko_ep_id:
                    msg = "Missing Shoko Episode ID in cross-reference. Skipping."
                    logging.warning("  %s", msg)
                    unmatched_report.append(f"File: '{original_filename}' | ID: {shoko_file_id} | Reason: {msg}")
                    continue
                
                full_episode_details = self.shoko_client.get_episode_details(shoko_ep_id)
                if not full_episode_details:
                    msg = "Could not fetch full episode details from Shoko. Skipping."
                    logging.warning("  %s", msg)
                    unmatched_report.append(f"File: '{original_filename}' | ID: {shoko_file_id} | Reason: {msg}")
                    continue

                tmdb_ids = full_episode_details.get('IDs', {}).get('TMDB', {})
                tmdb_movie_ids = tmdb_ids.get('Movie', [])
                tmdb_episode_ids = tmdb_ids.get('Episode', [])
                anidb_type = full_episode_details.get('AniDB', {}).get('Type')
                shoko_ep_title = full_episode_details.get('Name')
                logging.debug("  AniDB Type: '%s', Title: '%s'", anidb_type, shoko_ep_title)
                
                subfolder_path, final_filename = self._determine_path_and_filename(
                    full_episode_details, original_filename, series_id_data
                )

                if not subfolder_path or not final_filename:
                    msg = "Could not determine destination path or filename. Skipping."
                    logging.warning(f"  {msg}")
                    unmatched_report.append(f"File: '{original_filename}' | ID: {shoko_file_id} | Reason: {msg}")
                    continue

                destination_file_path = os.path.join(subfolder_path, final_filename)

                relative_path_from_shoko = file_data['Locations'][0]['RelativePath']
                normalized_path_for_splitting = relative_path_from_shoko.replace('\\', '/')
                path_components = normalized_path_for_splitting.split('/')
                os_native_relative_path = os.path.join(*path_components)
                source_file_path = os.path.join(self.config['directories']['source_root'], os_native_relative_path)
                
                all_successful = self.file_manager.process_file_group(source_file_path, destination_file_path, dir_cache)
                
                if all_successful and not self.args.dry_run:
                    logging.info("  > Successfully processed group for '%s'. Recording in database.", original_filename)
                    self.db_manager.add_processed_file(shoko_file_id, destination_file_path)

            except Exception as e:
                logging.error("An unexpected error occurred processing file ID %d: %s", shoko_file_id, e, exc_info=self.args.debug)
                unmatched_report.append(f"File ID: {shoko_file_id} | Reason: Unexpected script error - {e}")

        if unmatched_report:
            report_path = self.config['paths']['unmatched_report']
            logging.info("Writing %d unmatched items to report file: %s", len(unmatched_report), report_path)
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write("--- Unmatched Items Report ---\n")
                for line in unmatched_report:
                    f.write(f"{line}\n")
                    
        logging.info("--- Add/Update Run Finished ---")

    def _determine_path_and_filename(self, full_episode_details, original_filename, series_id_data):
        """
        Determines the final destination path and filename for a media file.
        Returns a tuple of (subfolder_path, final_filename).
        """
        tmdb_ids = full_episode_details.get('IDs', {}).get('TMDB', {})
        tmdb_movie_ids = tmdb_ids.get('Movie', [])
        
        if tmdb_movie_ids:
            return self._handle_movie_pathing(full_episode_details, original_filename, tmdb_movie_ids[0])
        else:
            return self._handle_show_pathing(full_episode_details, original_filename, series_id_data)

    def _handle_movie_pathing(self, full_episode_details, original_filename, tmdb_movie_id):
        """Determines path and filename for a movie."""
        logging.debug("  --- Processing as Movie ---")
        logging.info("    Identified as MOVIE via TMDb ID: %d", tmdb_movie_id)

        movie_details = None
        shoko_tmdb_movie_data = full_episode_details.get('TMDB', {}).get('Movies', [])
        if shoko_tmdb_movie_data and shoko_tmdb_movie_data[0].get('ID') == tmdb_movie_id:
            logging.info("      > Found full movie data directly from Shoko. Skipping TMDb API call.")
            shoko_movie_info = shoko_tmdb_movie_data[0]
            movie_details = {
                'title': shoko_movie_info.get('Title'),
                'release_date': shoko_movie_info.get('ReleasedAt')
            }
        
        if not movie_details:
            logging.info("      > Shoko did not provide full data. Querying TMDb API as a fallback...")
            movie_details = self.tmdb_client.get_movie_details(tmdb_movie_id)

        if not movie_details:
            logging.warning("  Failed to get TMDb details for Movie ID %d. Skipping.", tmdb_movie_id)
            return None, None

        movie_title = movie_details.get('title')
        movie_year = (movie_details.get('release_date') or '').split('-')[0]
        movie_title_cleaned = self._clean_filename(movie_title)
        movie_folder_name = f"{movie_title_cleaned} ({movie_year})"
        
        dest_movies = self.config['directories'].get('destination_movies') or self.config['directories']['destination']
        subfolder_path = os.path.join(dest_movies, movie_folder_name)
        final_filename = f"{movie_folder_name}{os.path.splitext(original_filename)[1]}"
        return subfolder_path, final_filename

    def _handle_show_pathing(self, full_episode_details, original_filename, series_id_data):
        """Determines path and filename for a TV show episode or extra."""
        logging.debug("  --- Processing as TV Show / Extra ---")
        try:
            tmdb_show_id = series_id_data[0]['SeriesID']['TMDB']['Show'][0]
        except (KeyError, IndexError):
            logging.warning("  Could not find a TMDb Show ID link in Shoko's cross-reference data. Skipping.")
            return None, None

        logging.debug("    > Fetching series details for TMDb ID %d...", tmdb_show_id)
        tmdb_series_data = self.tmdb_client.get_series_details(tmdb_show_id)
        if not tmdb_series_data:
            logging.warning("  Cannot process because TMDb series data could not be fetched for show ID %d.", tmdb_show_id)
            return None, None

        found_episode = self._find_tv_episode(full_episode_details, tmdb_show_id, tmdb_series_data)

        series_title_cleaned = self._clean_filename(tmdb_series_data.get('name'))
        series_year_cleaned = (tmdb_series_data.get('first_air_date') or '').split('-')[0]
        show_folder_name = f"{series_title_cleaned} ({series_year_cleaned})"
        dest_shows = self.config['directories']['destination']

        if found_episode: # Matched to a specific TV episode
            episode_title_cleaned = self._clean_filename(found_episode.get('name'))
            season_num_str = str(found_episode.get('season_number')).zfill(2)
            episode_num_str = str(found_episode.get('episode_number')).zfill(2)

            subfolder_path = os.path.join(dest_shows, show_folder_name, f"Season {season_num_str}")
            final_filename = f"{show_folder_name} - S{season_num_str}E{episode_num_str} - {episode_title_cleaned}{os.path.splitext(original_filename)[1]}"
        else: # Not matched, treat as an extra or skip
            anidb_type = full_episode_details.get('AniDB', {}).get('Type')

            # If a 'Normal' episode couldn't be matched by ID or title, it's truly unmatched.
            if anidb_type == 'Normal':
                return None, None

            shoko_ep_title = full_episode_details.get('Name')
            logging.info("    File could not be matched to a TV episode. Treating as an EXTRA of type '%s'.", anidb_type)

            extra_type_folder = "Other"
            if anidb_type == 'Trailer':
                extra_type_folder = "Trailers"
            elif anidb_type in ['Special', 'Credits', 'Parody']:
                extra_type_folder = "Featurettes"
            
            subfolder_path = os.path.join(dest_shows, show_folder_name, extra_type_folder)
            descriptive_filename = self._clean_filename(shoko_ep_title or os.path.splitext(original_filename)[0])
            final_filename = f"{descriptive_filename}{os.path.splitext(original_filename)[1]}"

        return subfolder_path, final_filename

    def _find_tv_episode(self, full_episode_details, tmdb_show_id, tmdb_series_data):
        """Finds a TV episode by direct ID or falls back to title matching."""
        tmdb_episode_ids = full_episode_details.get('IDs', {}).get('TMDB', {}).get('Episode', [])
        
        # --- Direct ID Match ---
        if tmdb_episode_ids:
            tmdb_episode_id = tmdb_episode_ids[0]
            logging.info("    Identified as TV EPISODE via TMDb ID: %d", tmdb_episode_id)

            shoko_tmdb_ep_data = full_episode_details.get('TMDB', {}).get('Episodes', [])
            if shoko_tmdb_ep_data and shoko_tmdb_ep_data[0].get('ID') == tmdb_episode_id:
                logging.info("      > Found full episode data directly from Shoko. Skipping TMDb season search.")
                shoko_ep_info = shoko_tmdb_ep_data[0]
                return {
                    'season_number': shoko_ep_info.get('SeasonNumber'),
                    'episode_number': shoko_ep_info.get('EpisodeNumber'),
                    'name': shoko_ep_info.get('Title')
                }

            logging.info("      > Shoko did not provide full data. Searching TMDb seasons as a fallback...")
            for season in tmdb_series_data.get('seasons', []):
                season_number = season.get('season_number')
                if season_number == 0: continue
                
                season_details = self.tmdb_client.get_season_details(tmdb_show_id, season_number)
                if not season_details: continue

                for episode in season_details:
                    if episode.get('id') == tmdb_episode_id:
                        logging.debug("        > Matched to S%sE%s", season_number, episode.get('episode_number'))
                        return episode

        # --- Title Match Fallback ---
        anidb_type = full_episode_details.get('AniDB', {}).get('Type')
        shoko_ep_title = full_episode_details.get('Name')
        if anidb_type == 'Normal':
            logging.warning("    No TMDb Episode ID link found for a 'Normal' episode. Attempting fallback match by title...")
            if not shoko_ep_title:
                logging.warning("      > Fallback failed: Shoko episode title is missing.")
                return None

            best_match = {'score': 0, 'episode': None}
            for season in sorted(tmdb_series_data.get('seasons', []), key=lambda s: s['season_number']):
                season_number = season.get('season_number')
                if season_number == 0: continue

                episodes_in_season = self.tmdb_client.get_season_details(tmdb_show_id, season_number)
                for episode_data in sorted(episodes_in_season, key=lambda e: e['episode_number']):
                    tmdb_ep_title = episode_data.get('name', '')
                    similarity = SequenceMatcher(None, shoko_ep_title.lower(), tmdb_ep_title.lower()).ratio()
                    
                    if similarity > best_match['score']:
                        best_match['score'] = similarity
                        best_match['episode'] = episode_data
            
            if best_match['score'] >= self.config['options']['title_similarity_threshold']:
                found_episode = best_match['episode']
                logging.info("    SUCCESS (Fallback Match): Matched to S%sE%s with similarity %.2f!", found_episode['season_number'], found_episode['episode_number'], best_match['score'])
                return found_episode

        return None

    def _run_cleanup(self):
        """Handles the logic for cleaning up stale files and database entries."""
        logging.info("--- Starting CLEANUP Run ---")
        if self.args.dry_run:
            logging.warning("DRY RUN MODE ENABLED: No files or database entries will be deleted.")

        all_shoko_file_ids = self.shoko_client.get_all_file_ids()
        stale_entries = self.db_manager.get_stale_entries(all_shoko_file_ids)
        
        logging.info("Found %d stale entries to clean up.", len(stale_entries))
        
        if not stale_entries:
            logging.info("No stale entries found.")
            return

        for entry in stale_entries:
            shoko_id = entry['shoko_file_id']
            dest_path = entry['destination_path']
            logging.info("Stale entry found for Shoko File ID: %d at '%s'", shoko_id, dest_path)
            if not self.args.dry_run:
                try:
                    self.file_manager.cleanup_stale_files(dest_path)
                    self.db_manager.remove_stale_entry(shoko_id)
                    logging.info("  > Database entry for Shoko File ID %d processed for removal.", shoko_id)
                except Exception as e:
                    logging.error("  > FAILED to remove link or DB entry. Error: %s", e)
            else:
                logging.info("  [DRY RUN] Would delete link and DB entry for Shoko File ID: %d", shoko_id)

        if not self.args.dry_run:
            self.file_manager.cleanup_empty_dirs(self.config['directories']['destination'])
            if self.config['directories'].get('destination_movies'):
                self.file_manager.cleanup_empty_dirs(self.config['directories']['destination_movies'])

        logging.info("--- Cleanup Run Finished ---")

    @staticmethod
    def _clean_filename(name):
        """Removes characters that are invalid in Windows and other filesystems."""
        return re.sub(r'[<>:"/\\|?*]', '-', name) if name else "Untitled"