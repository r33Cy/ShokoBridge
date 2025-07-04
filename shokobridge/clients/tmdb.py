# shokobridge/clients/tmdb.py
import logging
import json
import os
import time
import requests

class TMDbClient:
    """A client for interacting with The Movie Database (TMDb) API."""

    def __init__(self, api_key, cache_path, session):
        """
        Initializes the TMDbClient.

        :param api_key: The TMDb API key.
        :param cache_path: The file path for the TMDb cache.
        :param session: A requests.Session object for making HTTP requests.
        """
        self.api_key = api_key
        self.cache_path = cache_path
        self.session = session
        self.cache = self._load_cache()
        logging.debug("TMDbClient initialized.")

    def _load_cache(self):
        """Loads the TMDb cache from a JSON file."""
        if os.path.exists(self.cache_path):
            logging.debug("Loading TMDb cache from %s", self.cache_path)
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logging.error("Failed to load TMDb cache: %s. Starting with an empty cache.", e)
                return {}
        return {}

    def save_cache(self):
        """Saves the TMDb cache to a JSON file."""
        logging.debug("Saving TMDb cache to %s", self.cache_path)
        try:
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=4)
        except IOError as e:
            logging.error("Failed to save TMDb cache: %s", e)

    def get_series_details(self, tmdb_id):
        """Fetches series details from TMDb, using the cache."""
        cache_key = f"series_{tmdb_id}"
        if cache_key in self.cache:
            logging.debug("    > TMDb Series ID %d found in cache.", tmdb_id)
            return self.cache[cache_key]

        logging.info("    > Querying TMDb API for Series ID: %d", tmdb_id)
        params = {'api_key': self.api_key}
        try:
            time.sleep(0.25)
            response = self.session.get(f"https://api.themoviedb.org/3/tv/{tmdb_id}", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            logging.debug("    > TMDb Series ID %d fetched and cached.", tmdb_id)
            self.cache[cache_key] = data
            return data
        except requests.exceptions.RequestException as e:
            logging.error("    > FAILED to get TMDb series details for ID %d. Error: %s", tmdb_id, e)
            return None

    def get_movie_details(self, tmdb_id):
        """Fetches movie details from TMDb, using the cache."""
        cache_key = f"movie_{tmdb_id}"
        if cache_key in self.cache:
            logging.debug("    > TMDb Movie ID %d found in cache.", tmdb_id)
            return self.cache[cache_key]

        logging.info("    > Querying TMDb API for Movie ID: %d", tmdb_id)
        params = {'api_key': self.api_key}
        try:
            time.sleep(0.25)
            response = self.session.get(f"https://api.themoviedb.org/3/movie/{tmdb_id}", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            logging.debug("    > TMDb Movie ID %d fetched and cached.", tmdb_id)
            self.cache[cache_key] = data
            return data
        except requests.exceptions.RequestException as e:
            logging.error("    > FAILED to get TMDb movie details for ID %d. Error: %s", tmdb_id, e)
            return None

    def get_season_details(self, tmdb_id, season_number):
        """Fetches season details for a series from TMDb, using the cache."""
        cache_key = f"season_{tmdb_id}_{season_number}"
        if cache_key in self.cache:
            logging.debug("    > TMDb Season %d for Series %d found in cache.", season_number, tmdb_id)
            return self.cache[cache_key]

        logging.info("    > Querying TMDb API for Season %d details...", season_number)
        params = {'api_key': self.api_key}
        try:
            time.sleep(0.25)
            response = self.session.get(f"https://api.themoviedb.org/3/tv/{tmdb_id}/season/{season_number}", params=params, timeout=10)
            response.raise_for_status()
            data = response.json().get('episodes', [])
            logging.debug("    > TMDb Season %d for Series %d fetched and cached.", season_number, tmdb_id)
            self.cache[cache_key] = data
            return data
        except requests.exceptions.RequestException as e:
            logging.error("    > FAILED to get TMDb season %d for ID %d. Error: %s", season_number, tmdb_id, e)
            return []