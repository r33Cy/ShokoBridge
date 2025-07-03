# ==================================================================================
# ShokoBridge Automation Script v4.3 (Production)
#
# This script uses a stateful database (SQLite) to build and maintain a
# Plex-compatible library structure from a Shoko Server instance.
#
# Author: https://github.com/r33Cy
# Date: 2025-07-03
#
# ==================================================================================

import os
import requests
import time
import re
import json
import sqlite3
import logging
import argparse
import platform
import subprocess
import shutil
from logging.handlers import RotatingFileHandler
from difflib import SequenceMatcher

# --- 1. SCRIPT LOGIC (Configuration is now in config.json) ---

# --- Global Setup ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
DB_PATH = os.path.join(SCRIPT_DIR, "shokobridge_state.db")
CACHE_FILE_PATH = os.path.join(SCRIPT_DIR, "shokobridge_tmdb_cache.json")
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
UNMATCHED_REPORT_PATH = os.path.join(SCRIPT_DIR, "shokobridge_unmatched_report.txt")

session = requests.Session()

def load_config():
    """Loads configuration from config.json."""
    logging.debug("Loading configuration from %s", CONFIG_PATH)
    if not os.path.exists(CONFIG_PATH):
        logging.critical(f"FATAL: Configuration file not found at {CONFIG_PATH}")
        return None
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.critical(f"FATAL: Failed to read or parse config.json. Error: {e}")
        return None

def setup_logging(debug_mode):
    level = logging.DEBUG if debug_mode else logging.INFO
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file_path = os.path.join(LOG_DIR, "shokobridge.log")
    
    logger = logging.getLogger()
    logger.setLevel(level)
    
    if logger.hasHandlers():
        logger.handlers.clear()
        
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(ch_formatter)
    logger.addHandler(ch)

    fh = RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
    fh.setLevel(level)
    fh_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(fh_formatter)
    logger.addHandler(fh)
    
    logging.info("Logging initialized.")
    if debug_mode:
        logging.debug("Debug mode enabled.")

def setup_database():
    logging.debug("Setting up database at %s", DB_PATH)
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_files (
                shoko_file_id INTEGER PRIMARY KEY,
                destination_path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
        logging.info("Database initialized successfully.")
    except sqlite3.Error as e:
        logging.critical(f"Database setup failed: {e}")
        raise

def load_cache():
    if os.path.exists(CACHE_FILE_PATH):
        logging.debug("Loading TMDb cache from %s", CACHE_FILE_PATH)
        with open(CACHE_FILE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_cache(cache_data):
    logging.debug("Saving TMDb cache to %s", CACHE_FILE_PATH)
    with open(CACHE_FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, indent=4)

def get_windows_host_ip():
    if platform.system() == "Linux" and "microsoft" in platform.release().lower():
        try:
            command = "ip route | grep default | awk '{print $3}'"
            result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
            ip = result.stdout.strip()
            if ip:
                logging.info(f"Dynamically found Windows host IP: {ip}")
                return ip
        except Exception as e:
            logging.error(f"Error trying to find host IP: {e}")
            return None
    return "127.0.0.1"

def check_shoko_connection(config):
    shoko_url = config['shoko']['url']
    logging.info("Checking connection to Shoko Server at %s...", shoko_url)
    try:
        response = requests.get(f"{shoko_url}/api/v3/Init/Version", timeout=10)
        response.raise_for_status()
        logging.info("Shoko Server connection successful.")
        return True
    except requests.exceptions.RequestException as e:
        logging.critical(f"Could not connect to Shoko Server. Error: {e}")
        return False

def get_all_shoko_file_ids(config):
    shoko_url = config['shoko']['url']
    logging.info("Fetching all recognized file IDs from Shoko...")
    headers = {'apikey': config['shoko']['api_key']}
    params = {'pageSize': 0}
    try:
        response = session.get(f"{shoko_url}/api/v3/File", headers=headers, params=params, timeout=120)
        response.raise_for_status()
        files = response.json()['List']
        logging.info(f"Found {len(files)} total recognized files in Shoko.")
        return [f['ID'] for f in files]
    except requests.exceptions.RequestException as e:
        logging.error(f"Could not fetch file list from Shoko. Error: {e}")
        return []
        
def get_shoko_file_details(config, shoko_file_id):
    shoko_url = config['shoko']['url']
    logging.debug(f"Fetching full details for Shoko File ID: {shoko_file_id}")
    headers = {'apikey': config['shoko']['api_key']}
    params = {'include': 'MediaInfo,XRefs'}
    try:
        response = session.get(f"{shoko_url}/api/v3/File/{shoko_file_id}", headers=headers, params=params, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Could not fetch details for file ID {shoko_file_id}. Error: {e}")
        return None

def get_shoko_episode_details(config, episode_id):
    shoko_url = config['shoko']['url']
    logging.debug(f"  Fetching full Shoko Episode details for ID: {episode_id}")
    params = {'includeDataFrom': 'AniDB,TMDB'}
    headers = {'apikey': config['shoko']['api_key']}
    try:
        response = session.get(f"{shoko_url}/api/v3/Episode/{episode_id}", headers=headers, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"  Could not get Shoko Episode details for ID {episode_id}. Error: {e}")
        return None

def get_tmdb_series_details(config, tmdb_id, cache):
    cache_key = f"series_{tmdb_id}"
    if cache_key in cache:
        logging.debug(f"TMDb Series ID {tmdb_id} found in cache.")
        return cache[cache_key]
    
    logging.info(f"Querying TMDb API for Series ID: {tmdb_id}")
    params = {'api_key': config['tmdb']['api_key']}
    try:
        time.sleep(0.25)
        response = session.get(f"https://api.themoviedb.org/3/tv/{tmdb_id}", params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        cache[cache_key] = data
        logging.debug(f"TMDb Series ID {tmdb_id} fetched and cached.")
        return data
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to get TMDb series details for ID {tmdb_id}. Error: {e}")
        return None

def get_tmdb_movie_details(config, tmdb_id, cache):
    """Fetches movie details from TMDb API, using a cache to avoid redundant calls."""
    cache_key = f"movie_{tmdb_id}"
    if cache_key in cache:
        logging.debug(f"TMDb Movie ID {tmdb_id} found in cache.")
        return cache[cache_key]
    
    logging.info(f"Querying TMDb API for Movie ID: {tmdb_id}")
    params = {'api_key': config['tmdb']['api_key']}
    try:
        time.sleep(0.25) # Adhere to TMDb rate limiting
        response = session.get(f"https://api.themoviedb.org/3/movie/{tmdb_id}", params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        cache[cache_key] = data
        logging.debug(f"TMDb Movie ID {tmdb_id} fetched and cached.")
        return data
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to get TMDb movie details for ID {tmdb_id}. Error: {e}")
        return None

def get_tmdb_season_details(config, tmdb_id, season_number, cache):
    cache_key = f"season_{tmdb_id}_{season_number}"
    if cache_key in cache:
        logging.debug(f"  TMDb Season {season_number} for Series {tmdb_id} found in cache.")
        return cache[cache_key]

    logging.info(f"  > Querying TMDb API for Season {season_number} details...")
    params = {'api_key': config['tmdb']['api_key']}
    try:
        time.sleep(0.25)
        response = session.get(f"https://api.themoviedb.org/3/tv/{tmdb_id}/season/{season_number}", params=params, timeout=10)
        response.raise_for_status()
        data = response.json().get('episodes', [])
        cache[cache_key] = data
        logging.debug(f"  TMDb Season {season_number} for Series {tmdb_id} fetched and cached.")
        return data
    except requests.exceptions.RequestException as e:
        logging.error(f"  Failed to get TMDb season {season_number} for ID {tmdb_id}. Error: {e}")
        return []

def get_preferred_title(config, names_list):
    if not isinstance(names_list, list):
        logging.warning("get_preferred_title received a non-list object. Returning 'Unknown'.")
        return "Unknown"
    titles = {name['Language']: name['Name'] for name in names_list}
    for lang in config['options']['language_priority']:
        if lang in titles and titles[lang]:
            return titles[lang]
    return next(iter(titles.values()), "Unknown")

def clean_filename(name):
    """Removes characters that are invalid in Windows and other filesystems."""
    return re.sub(r'[<>:"/\\|?*]', '-', name) if name else "Untitled"

def get_processed_files_from_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT shoko_file_id FROM processed_files")
    ids = {row[0] for row in cursor.fetchall()}
    conn.close()
    logging.debug(f"Loaded {len(ids)} processed file IDs from database.")
    return ids

def run_add_new(args, config):
    logging.info("--- Starting ADD/UPDATE Run ---")
    if args.dry_run:
        logging.warning("DRY RUN MODE ENABLED: No changes will be made to the filesystem or database.")

    # Get destination paths from config
    dest_shows = config['directories']['destination']
    dest_movies = config['directories'].get('destination_movies') or dest_shows

    tmdb_cache = load_cache()
    processed_file_ids = get_processed_files_from_db()
    all_shoko_file_ids = get_all_shoko_file_ids(config)

    files_to_process_ids = [fid for fid in all_shoko_file_ids if fid not in processed_file_ids]
    logging.info(f"Found {len(files_to_process_ids)} new files to process.")
    
    if not files_to_process_ids:
        logging.info("No new files to process. Library is up to date.")
        save_cache(tmdb_cache)
        return

    unmatched_report = []

    for shoko_file_id in files_to_process_ids:
        try:
            file_data = get_shoko_file_details(config, shoko_file_id)
            if not file_data:
                logging.warning(f"Could not get details for Shoko File ID {shoko_file_id}. Skipping.")
                unmatched_report.append(f"File ID: {shoko_file_id} | Reason: Failed to fetch file details from Shoko.")
                continue

            original_filename = os.path.basename(file_data['Locations'][0]['RelativePath'])
            logging.debug(f"\n--- Processing File ID: {shoko_file_id} | File: '{original_filename}' ---")
            
            series_id_data = file_data.get('SeriesIDs', [])
            if not series_id_data:
                msg = "File is not linked to any series in Shoko. Skipping."
                logging.warning(f"  {msg}")
                unmatched_report.append(f"File: '{original_filename}' | ID: {shoko_file_id} | Reason: {msg}")
                continue
            
            episode_id_data = series_id_data[0].get('EpisodeIDs', [])
            if not episode_id_data:
                msg = "File is not linked to any episodes in Shoko. Skipping."
                logging.warning(f"  {msg}")
                unmatched_report.append(f"File: '{original_filename}' | ID: {shoko_file_id} | Reason: {msg}")
                continue
            
            # Get full Shoko episode details upfront for type and title info
            shoko_ep_id = episode_id_data[0].get('ID')
            if not shoko_ep_id:
                msg = "Missing Shoko Episode ID in cross-reference. Skipping."
                logging.warning(f"  {msg}")
                unmatched_report.append(f"File: '{original_filename}' | ID: {shoko_file_id} | Reason: {msg}")
                continue
            
            full_episode_details = get_shoko_episode_details(config, shoko_ep_id)
            if not full_episode_details:
                msg = "Could not fetch full episode details from Shoko. Skipping."
                logging.warning(f"  {msg}")
                unmatched_report.append(f"File: '{original_filename}' | ID: {shoko_file_id} | Reason: {msg}")
                continue

            # --- New Media Type Identification Logic ---
            tmdb_ids = full_episode_details.get('IDs', {}).get('TMDB', {})
            tmdb_movie_ids = tmdb_ids.get('Movie', [])
            tmdb_episode_ids = tmdb_ids.get('Episode', [])
            anidb_type = full_episode_details.get('AniDB', {}).get('Type')
            shoko_ep_title = full_episode_details.get('Name')
            logging.debug(f"  AniDB Type: '{anidb_type}', Title: '{shoko_ep_title}'")
            
            subfolder_path = None
            final_filename = None
            tmdb_series_data = None
            
            # --- 1. MOVIE CHECK ---
            if tmdb_movie_ids:
                tmdb_movie_id = tmdb_movie_ids[0]
                logging.info(f"  Identified as MOVIE via TMDb ID: {tmdb_movie_id}")

                movie_details = None
                # OPTIMIZATION: Check for rich TMDb data from Shoko first
                shoko_tmdb_movie_data = full_episode_details.get('TMDB', {}).get('Movies', [])
                if shoko_tmdb_movie_data and shoko_tmdb_movie_data[0].get('ID') == tmdb_movie_id:
                    logging.info("    > Found full movie data directly from Shoko. Skipping TMDb API call.")
                    shoko_movie_info = shoko_tmdb_movie_data[0]
                    movie_details = {
                        'title': shoko_movie_info.get('Title'),
                        'release_date': shoko_movie_info.get('ReleasedAt')
                    }
                
                # Fallback: If Shoko didn't provide full data, query TMDb API
                if not movie_details:
                    logging.info("    > Shoko did not provide full data. Querying TMDb API as a fallback...")
                    movie_details = get_tmdb_movie_details(config, tmdb_movie_id, tmdb_cache)

                if not movie_details:
                    msg = f"Failed to get TMDb details for Movie ID {tmdb_movie_id}. Skipping."
                    logging.warning(f"  {msg}")
                    unmatched_report.append(f"File: '{original_filename}' | ID: {shoko_file_id} | Reason: {msg}")
                    continue

                movie_title = movie_details.get('title')
                movie_year = (movie_details.get('release_date') or '').split('-')[0]
                movie_title_cleaned = clean_filename(movie_title)
                movie_folder_name = f"{movie_title_cleaned} ({movie_year})"
                
                subfolder_path = os.path.join(dest_movies, movie_folder_name)
                final_filename = f"{movie_folder_name}{os.path.splitext(original_filename)[1]}"

            # --- 2. TV SHOW & EXTRAS CHECK ---
            else:
                tmdb_show_id = series_id_data[0]['SeriesID']['TMDB']['Show'][0]
                tmdb_series_data = get_tmdb_series_details(config, tmdb_show_id, tmdb_cache)
                if not tmdb_series_data:
                    msg = f"Cannot process TV/Extra because TMDb series data could not be fetched for show ID {tmdb_show_id}. Skipping."
                    logging.warning(f"  {msg}")
                    unmatched_report.append(f"File: '{original_filename}' | ID: {shoko_file_id} | Reason: {msg}")
                    continue
                
                found_episode = None
                # --- 2a. TV EPISODE CHECK (Direct ID) ---
                if tmdb_episode_ids:
                    tmdb_episode_id = tmdb_episode_ids[0]
                    logging.info(f"  Identified as TV EPISODE via TMDb ID: {tmdb_episode_id}")

                    # OPTIMIZATION: Check for rich TMDb data from Shoko first
                    shoko_tmdb_ep_data = full_episode_details.get('TMDB', {}).get('Episodes', [])
                    if shoko_tmdb_ep_data and shoko_tmdb_ep_data[0].get('ID') == tmdb_episode_id:
                        logging.info("    > Found full episode data directly from Shoko. Skipping TMDb season search.")
                        shoko_ep_info = shoko_tmdb_ep_data[0]
                        found_episode = {
                            'season_number': shoko_ep_info.get('SeasonNumber'),
                            'episode_number': shoko_ep_info.get('EpisodeNumber'),
                            'name': shoko_ep_info.get('Title')
                        }

                    # Fallback: If Shoko didn't provide full data, search TMDb seasons
                    if not found_episode:
                        logging.info("    > Shoko did not provide full data. Searching TMDb seasons as a fallback...")
                        for season in tmdb_series_data.get('seasons', []):
                            season_number = season.get('season_number')
                            if season_number == 0: continue # Specials are handled by AniDB type later
                            
                            season_details = get_tmdb_season_details(config, tmdb_show_id, season_number, tmdb_cache)
                            if not season_details: continue

                            for episode in season_details:
                                if episode.get('id') == tmdb_episode_id:
                                    found_episode = episode
                                    logging.debug(f"    > Matched to S{season_number}E{episode.get('episode_number')}")
                                    break
                            if found_episode: break

                # --- 2b. TV EPISODE CHECK (Title Fallback) ---
                if not found_episode and anidb_type == 'Normal':
                    logging.warning(f"  No TMDb Episode ID link found for a 'Normal' episode. Attempting fallback match by title...")
                    if not shoko_ep_title:
                        logging.warning("    > Fallback failed: Shoko episode title is missing.")
                    else:
                        best_match = {'score': 0, 'episode': None}
                        for season in sorted(tmdb_series_data.get('seasons', []), key=lambda s: s['season_number']):
                            season_number = season.get('season_number')
                            if season_number == 0: continue

                            episodes_in_season = get_tmdb_season_details(config, tmdb_show_id, season_number, tmdb_cache)
                            for episode_data in sorted(episodes_in_season, key=lambda e: e['episode_number']):
                                tmdb_ep_title = episode_data.get('name', '')
                                similarity = SequenceMatcher(None, shoko_ep_title.lower(), tmdb_ep_title.lower()).ratio()
                                
                                if similarity > best_match['score']:
                                    best_match['score'] = similarity
                                    best_match['episode'] = episode_data
                        
                        if best_match['score'] >= config['options']['title_similarity_threshold']:
                            found_episode = best_match['episode']
                            logging.info(f"  SUCCESS (Fallback Match): Matched to S{found_episode['season_number']}E{found_episode['episode_number']} with similarity {best_match['score']:.2f}!")

                # --- 2c. PATH & FILENAME CONSTRUCTION (TV & Extras) ---
                series_title_cleaned = clean_filename(tmdb_series_data.get('name'))
                series_year_cleaned = (tmdb_series_data.get('first_air_date') or '').split('-')[0]
                show_folder_name = f"{series_title_cleaned} ({series_year_cleaned})"

                if found_episode:
                    # This is a matched TV Episode
                    episode_title_cleaned = clean_filename(found_episode.get('name'))
                    season_num_str = str(found_episode.get('season_number')).zfill(2)
                    episode_num_str = str(found_episode.get('episode_number')).zfill(2)

                    subfolder_path = os.path.join(dest_shows, show_folder_name, f"Season {season_num_str}")
                    final_filename = f"{show_folder_name} - S{season_num_str}E{episode_num_str} - {episode_title_cleaned}{os.path.splitext(original_filename)[1]}"
                else:
                    # This is an Extra
                    logging.info(f"  File could not be matched to a TV episode. Treating as an EXTRA of type '{anidb_type}'.")
                    extra_type_folder = "Other" # Default folder for unknown extra types
                    if anidb_type == 'Trailer':
                        extra_type_folder = "Trailers"
                    elif anidb_type in ['Special', 'Credits', 'Parody', 'Other']: # AniDB 'Other' is usually an extra
                        extra_type_folder = "Featurettes"
                    
                    subfolder_path = os.path.join(dest_shows, show_folder_name, extra_type_folder)
                    descriptive_filename = clean_filename(shoko_ep_title or os.path.splitext(original_filename)[0])
                    final_filename = f"{descriptive_filename}{os.path.splitext(original_filename)[1]}"

            destination_file_path = os.path.join(subfolder_path, final_filename)

            # Normalize the source path for cross-platform compatibility
            relative_path_from_shoko = file_data['Locations'][0]['RelativePath']
            normalized_path_for_splitting = relative_path_from_shoko.replace('\\', '/')
            path_components = normalized_path_for_splitting.split('/')
            os_native_relative_path = os.path.join(*path_components)
            source_file_path = os.path.join(config['directories']['source_root'], os_native_relative_path)
            

            # --- Symlink Target Path Logic ---
            symlink_target_path = source_file_path
            if config['options'].get('use_relative_symlinks', False):
                symlink_target_path = os.path.relpath(source_file_path, start=os.path.dirname(destination_file_path))
                logging.debug("  Calculated relative symlink target.")
            elif config.get('path_mappings'):
                for mapping in config['path_mappings']:
                    script_path = mapping.get('script_path')
                    plex_path = mapping.get('plex_path')
                    if script_path and plex_path and symlink_target_path.startswith(script_path):
                        symlink_target_path = symlink_target_path.replace(script_path, plex_path, 1)
                        logging.debug(f"  Applied path mapping: '{script_path}' -> '{plex_path}'")
                        break
            
            logging.debug(f"    Script-visible Source Path: {source_file_path}")
            logging.debug(f"    Plex-visible Symlink Target: {symlink_target_path}")
            logging.debug(f"    Destination Path: {destination_file_path}")

            if not args.dry_run:
                try:
                    os.makedirs(subfolder_path, exist_ok=True)
                    if not os.path.exists(destination_file_path):
                        link_type = config['options'].get('link_type', 'symlink')
                        if link_type == 'copy':
                            shutil.copy2(source_file_path, destination_file_path)
                            logging.info(f"    + COPIED and recorded: {os.path.basename(destination_file_path)}")
                        elif link_type == 'hardlink':
                            os.link(source_file_path, destination_file_path)
                            logging.info(f"    + HARD-LINKED and recorded: {os.path.basename(destination_file_path)}")
                        elif link_type == 'move':
                            shutil.move(source_file_path, destination_file_path)
                            logging.info(f"    + MOVED and recorded: {os.path.basename(destination_file_path)}")
                        else: # symlink is the default
                            os.symlink(symlink_target_path, destination_file_path)
                            logging.info(f"    + SYM-LINKED and recorded: {os.path.basename(destination_file_path)}")
                        
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO processed_files (shoko_file_id, destination_path) VALUES (?, ?)", (shoko_file_id, destination_file_path))
                        conn.commit()
                        conn.close()
                except Exception as e:
                    logging.error(f"    - FAILED to link or record {source_file_path}. Error: {e}", exc_info=args.debug)
            else:
                logging.info(f"    [DRY RUN] Would {config['options'].get('link_type', 'symlink')} and record: {destination_file_path}")

        except Exception as e:
            logging.error(f"An unexpected error occurred processing file ID {shoko_file_id}: {e}", exc_info=args.debug)
            unmatched_report.append(f"File ID: {shoko_file_id} | Reason: Unexpected script error - {e}")

    save_cache(tmdb_cache)
    
    if unmatched_report:
        logging.info(f"Writing {len(unmatched_report)} unmatched items to report file.")
        with open(UNMATCHED_REPORT_PATH, 'w', encoding='utf-8') as f:
            f.write("--- Unmatched Items Report ---\n")
            for line in unmatched_report:
                f.write(f"{line}\n")
                
    logging.info("--- Add/Update Run Finished ---")


def run_cleanup(args, config):
    logging.info("--- Starting CLEANUP Run ---")
    if args.dry_run:
        logging.warning("DRY RUN MODE ENABLED: No files or database entries will be deleted.")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT shoko_file_id, destination_path FROM processed_files")
    db_files = cursor.fetchall()
    
    all_shoko_file_ids = get_all_shoko_file_ids(config)
    stale_entries = [entry for entry in db_files if entry[0] not in all_shoko_file_ids]
    
    logging.info(f"Found {len(stale_entries)} stale entries to clean up.")
    
    if not stale_entries:
        logging.info("No stale entries found.")
        conn.close()
        return

    for shoko_id, dest_path in stale_entries:
        logging.info(f"Stale entry found for Shoko File ID: {shoko_id} at '{dest_path}'")
        if not args.dry_run:
            try:
                if os.path.exists(dest_path):
                    os.remove(dest_path)
                    logging.info("  > Link successfully removed.")
                else:
                    logging.warning("  > Link path not found, removing from DB anyway.")
                
                cursor.execute("DELETE FROM processed_files WHERE shoko_file_id = ?", (shoko_id,))
                logging.info(f"  > Database entry for Shoko File ID {shoko_id} removed.")
            except Exception as e:
                logging.error(f"  > FAILED to remove link or DB entry. Error: {e}")
        else:
            logging.info(f"  [DRY RUN] Would delete link and DB entry for Shoko File ID: {shoko_id}")
    
    if not args.dry_run:
        conn.commit()
    conn.close()
    
    if not args.dry_run:
        logging.info("Cleaning up empty directories in destination...")
        for dirpath, dirnames, filenames in os.walk(config['directories']['destination'], topdown=False):
            if not dirnames and not filenames:
                try:
                    os.rmdir(dirpath)
                    logging.debug(f"  > Removed empty directory: {dirpath}")
                except OSError as e:
                    logging.error(f"  > FAILED to remove empty directory {dirpath}. Error: {e}")

    logging.info("--- Cleanup Run Finished ---")


def main():
    parser = argparse.ArgumentParser(
        description="ShokoBridge: A stateful Shoko to Plex Hardlink Automation Script.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--cleanup', action='store_true', help="Run in cleanup mode to remove dead links.")
    parser.add_argument('--dry-run', action='store_true', help="Simulate a run without making any filesystem or DB changes.")
    parser.add_argument('--debug', action='store_true', help="Enable verbose debug logging.")
    
    args = parser.parse_args()
    
    setup_logging(args.debug)
    config = load_config()
    if not config:
        return

    setup_database()

    shoko_url = config['shoko']['url']
    if 'windows.host' in shoko_url:
        host_ip = get_windows_host_ip()
        if host_ip:
            config['shoko']['url'] = shoko_url.replace('windows.host', host_ip)
        else:
            logging.critical("Could not resolve 'windows.host'. Please set the Shoko IP manually in the config. Exiting.")
            return

    if not check_shoko_connection(config):
        logging.critical("Exiting due to failed connection check.")
        return

    if args.cleanup:
        run_cleanup(args, config)
    else:
        run_add_new(args, config)

if __name__ == "__main__":
    main()
