# ==================================================================================
# ShokoBridge Automation Script v5.1.0
#
# This script uses a stateful database (SQLite) to build and maintain a
# Plex-compatible library structure from a Shoko Server instance.
#
# Author: https://github.com/r33Cy
# Date: 2025-07-03
#
# ==================================================================================

import os
import json
import logging
import argparse

from shokobridge.bridge import ShokoBridge
from shokobridge.utils import setup_logging

# --- Global Setup ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT_VERSION = "v5.1.0"

def load_config(config_path):
    """Loads configuration from config.json."""
    logging.debug("Loading configuration from %s", config_path)
    if not os.path.exists(config_path):
        logging.critical("FATAL: Configuration file not found at %s", config_path)
        return None
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.critical("FATAL: Failed to read or parse config.json. Error: %s", e)
        return None

def main():
    parser = argparse.ArgumentParser(
        description="ShokoBridge: A stateful Shoko to Plex Hardlink Automation Script.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--cleanup', action='store_true', help="Run in cleanup mode to remove dead links.")
    parser.add_argument('--dry-run', action='store_true', help="Simulate a run without making any filesystem or DB changes.")
    parser.add_argument('--debug', action='store_true', help="Enable verbose debug logging.")

    args = parser.parse_args()

    # Define data paths
    data_dir = os.path.join(SCRIPT_DIR, "data")
    log_dir = os.path.join(data_dir, "logs")
    db_path = os.path.join(data_dir, "shokobridge_state.db")
    cache_path = os.path.join(data_dir, "shokobridge_tmdb_cache.json")
    report_path = os.path.join(data_dir, "shokobridge_unmatched_report.txt")
    os.makedirs(data_dir, exist_ok=True)

    # Initialize logging first
    setup_logging(log_dir, args.debug)

    logging.info("--- ShokoBridge %s ---", SCRIPT_VERSION)

    config_path = os.path.join(SCRIPT_DIR, "config.json")
    config = load_config(config_path)
    if not config:
        return

    # Inject dynamic paths into config for the application class to use
    config['paths'] = {
        'db': db_path,
        'cache': cache_path,
        'unmatched_report': report_path
    }

    try:
        # Instantiate and run the main application
        app = ShokoBridge(args, config)
        app.run()
    except Exception as e:
        logging.critical("An unhandled exception occurred: %s", e, exc_info=True)
        raise

if __name__ == "__main__":
    main()
