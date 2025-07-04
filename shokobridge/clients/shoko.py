# shokobridge/clients/shoko.py
import logging
import requests

class ShokoClient:
    """A client for interacting with the Shoko Server API."""

    def __init__(self, url, api_key, session):
        """
        Initializes the ShokoClient.

        :param url: The base URL of the Shoko server.
        :param api_key: The API key for authentication.
        :param session: A requests.Session object for making HTTP requests.
        """
        self.url = url
        self.api_key = api_key
        self.session = session
        self.headers = {'apikey': self.api_key}
        logging.debug("ShokoClient initialized for URL: %s", self.url)

    def check_connection(self):
        """Checks the connection to the Shoko Server."""
        logging.info("Checking connection to Shoko Server at %s...", self.url)
        try:
            response = self.session.get(f"{self.url}/api/v3/Init/Version", timeout=10)
            response.raise_for_status()
            logging.info("Shoko Server connection successful.")
            return True
        except requests.exceptions.RequestException as e:
            logging.critical("Could not connect to Shoko Server. Error: %s", e)
            return False

    def get_all_file_ids(self):
        """Fetches all recognized file IDs from Shoko."""
        logging.info("Fetching all recognized file IDs from Shoko...")
        params = {'pageSize': 0}
        try:
            response = self.session.get(f"{self.url}/api/v3/File", headers=self.headers, params=params, timeout=120)
            response.raise_for_status()
            files = response.json()['List']
            logging.info("Found %d total recognized files in Shoko.", len(files))
            return [f['ID'] for f in files]
        except requests.exceptions.RequestException as e:
            logging.error("Could not fetch file list from Shoko. Error: %s", e)
            return []

    def get_file_details(self, file_id):
        """Fetches detailed information for a specific file ID."""
        logging.debug("  Fetching file details for ID: %d", file_id)
        params = {'include': 'MediaInfo,XRefs'}
        try:
            response = self.session.get(f"{self.url}/api/v3/File/{file_id}", headers=self.headers, params=params, timeout=20)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error("Could not fetch details for file ID %d. Error: %s", file_id, e)
            return None

    def get_episode_details(self, episode_id):
        """Fetches detailed information for a specific episode ID."""
        logging.debug("  Fetching episode details for ID: %d", episode_id)
        params = {'includeDataFrom': 'AniDB,TMDB'}
        try:
            response = self.session.get(f"{self.url}/api/v3/Episode/{episode_id}", headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error("  Could not get Shoko Episode details for ID %d. Error: %s", episode_id, e)
            return None