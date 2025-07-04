# shokobridge/utils.py
import logging
import os
import platform
import subprocess
from logging.handlers import RotatingFileHandler


def setup_logging(log_dir, debug_mode):
    """Sets up console and rotating file logging."""
    level = logging.DEBUG if debug_mode else logging.INFO
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, "shokobridge.log")

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


def get_windows_host_ip():
    """If running in WSL, gets the IP of the Windows host, otherwise returns None."""
    if platform.system() == "Linux" and "microsoft" in platform.release().lower():
        logging.debug("WSL environment detected. Attempting to find Windows host IP...")
        try:
            result = subprocess.run("ip route | grep default | awk '{print $3}'", shell=True, capture_output=True, text=True, check=True)
            ip = result.stdout.strip()
            if ip:
                logging.info("Dynamically found Windows host IP: %s", ip)
            return ip if ip else None
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logging.error("Could not determine Windows host IP. Error: %s", e)
            return None
    return None