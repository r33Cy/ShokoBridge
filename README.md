# ShokoBridge

A robust, stateful automation script designed to bridge the gap between Shoko Server's AniDB-centric organization and Plex's media structure for both TV shows and movies. ShokoBridge creates a perfect, Plex-compatible library structure using your choice of file operations (`move`, `copy`, `hardlink`, or `symlink`), ensuring your anime library is beautifully organized and playable in any environment.

---

## Why ShokoBridge?

The official **Shoko Metadata** plugin was once the ideal way to integrate an anime library with Plex. However, support for legacy plugins and third-party scanners was officially removed, a change that fully impacted devices like the Nvidia Shield with Plex Media Server v1.41.0.8992.

This left the community without a direct integration method, creating a major problem:

*   **Plex's native scanner** requires TMDb-style naming (`Show/Season 01/S01E01.mkv`).
*   **Shoko's library** is organized by AniDB's absolute numbering.

This incompatibility means Plex cannot understand a raw Shoko library, leading to failed scans, incorrectly merged shows, and missing seasons—a problem especially felt on locked-down devices like the Nvidia Shield where alternative solutions are limited.

**ShokoBridge** is the definitive, modern solution. It acts as an intelligent integration layer:

1. It uses Shoko to reliably identify every file in your collection.
2. It leverages Shoko's built-in TMDb integration to get the official movie or season/episode structure for each file, minimizing external API calls.
3. It programmatically builds a perfect, Plex-compatible directory structure that Plex's **native scanner can understand**, using your configured file operation method.
4. It maintains a stateful database to only process new files and includes robust cleanup and logging features.

The result is a fully automated, "set it and forget it" system for a perfect anime library in Plex, no matter how complex your setup.

## Features

* **Flexible Deployment:** Supports both Docker for isolated, reproducible builds and traditional manual Python setups.
* **Centralized Data:** All persistent data—database, logs, cache, and reports—are stored in a single, mountable `data/` directory.
* **External Configuration:** All settings are managed in a simple `config.json` file.
* **Stateful Database:** Uses an SQLite database to keep track of processed files, ensuring it only works on new items.
* **Intelligent Matching:**
  * **Handles Movies & Shows:** Correctly identifies and separates anime movies from TV series.
  * **Optimized API Usage:** Leverages rich TMDb data from the Shoko API to minimize external calls.
  * **Robust Identification Hierarchy:** Uses TMDb Movie/Episode IDs for perfect accuracy.
  * **Smart Fallbacks:** If a direct ID match isn't possible, it falls back to title similarity for regular episodes and uses AniDB types to correctly categorize extras (Specials, Trailers, etc.).
* **Comprehensive File Handling:**
  * **Supplemental File Support:** Automatically finds and processes related files (e.g., `.srt`, `.ass`, `.nfo`) alongside the main video file.
  * **Transactional File Grouping:** Ensures that a media file and all its supplemental files are processed as a single unit. If any file fails, all changes for that group are rolled back.
  * **Flexible File Operations:** Choose between `move`, `copy`, `hardlink`, or `symlink`.
* **Advanced Pathing for Complex Setups:** Supports `use_relative_symlinks` and `path_mappings` for Docker, WSL, and NAS environments.
* **Robust Library Management:**
  * **Safe Operations:** `--cleanup` and `--dry-run` flags for predictable management.
  * **Thorough Cleanup:** The cleanup process removes stale links, their associated supplemental files, and any empty directories left behind.
  * **Detailed Logging:** Creates daily rolling log files with a `--debug` flag for verbose troubleshooting.
  * **API Caching & Reporting:** Caches TMDb results to minimize API calls and generates reports for any files it cannot map.
* **Cross-Platform:** Runs on any system that supports Docker or Python 3.13.


## Setup

ShokoBridge can be configured and run in two equally supported ways: **Docker** or **Manual Python Setup**. Choose the method that best fits your environment.

### 1. Get the Code

Clone the repository to your local machine:

```bash
git clone https://github.com/r33Cy/ShokoBridge.git
cd ShokoBridge
```

### 2. Configure `config.json`

Create a `config.json` file in the project root. Use the template below and fill in your details.

- **IMPORTANT:** The `shoko.url` must be the network-accessible IP address of your Shoko server (e.g., `http://192.168.1.100:8111`). Do not use `localhost`.
- The `source_root`, `destination`, and `destination_movies` paths should match your environment. For Docker, these are the paths *inside the container*. For manual setup, use the paths as seen by your OS.

```json
{
    "shoko": {
        "url": "http://<SHOKO_IP_ADDRESS>:8111",
        "api_key": ""
    },
    "tmdb": {
        "api_key": ""
    },
    "directories": {
        "source_root": "/anime",
        "destination": "/plex-shows",
        "destination_movies": "/plex-movies"
    },
    "path_mappings": [],
    "options": {
        "link_type": "hardlink",
        "use_relative_symlinks": false,
        "title_similarity_threshold": 0.8
    }
}
```

### 3. Choose Your Setup Method

You can now proceed with **either** Docker **or** Manual Python setup. Both are fully supported:

#### **A. Docker Setup**

1. **Configure `docker-compose.yml`:**
   Open the `docker-compose.yml` file that came with the repository. **Edit the volume paths on the left** to match the locations on your host machine.

   ```yaml
   version: '3.8'
   services:
     shokobridge:
       build: .
       container_name: shokobridge
       volumes:
         # Mount the config file (read-only)
         - ./config.json:/app/config.json:ro
         # Mount a single data directory for all persistent state
         - ./data:/app/data

         # --- IMPORTANT: Mount your media libraries ---
         # The path on the left is on your HOST machine.
         # The path on the right is inside the CONTAINER.
         # The container paths MUST match what's in your config.json
         - /path/on/host/to/anime:/anime:ro
         - /path/on/host/to/plex-shows:/plex-shows
         - /path/on/host/to/plex-movies:/plex-movies
   ```
   * **Note:** If using `hardlink` mode, your source and destination folders must be on the same filesystem/partition on your host machine.

2. **Build and Run:**
   Open a terminal in the project directory and use `docker-compose` to build the image and run the script.
   * **Initial Run:** `docker-compose run --rm shokobridge`
   * **Cleanup Run:** `docker-compose run --rm shokobridge --cleanup`
   * **Dry Run (Recommended First):** `docker-compose run --rm shokobridge --dry-run --debug`

   The first run will take a few minutes to build the Docker image. Subsequent runs will be much faster.

#### **B. Manual Python Setup**

1. **Prerequisites:**
   Ensure you have Python 3.13 and Git installed.

2. **Install Dependencies:**
   This project uses `pipenv` to manage dependencies.
   ```bash
   pip install pipenv
   pipenv install --deploy --ignore-pipfile
   ```

3. **Run the Script:**
   * **Initial Run:** `pipenv run python ShokoBridge.py`
   * **Cleanup Run:** `pipenv run python ShokoBridge.py --cleanup`
   * **Dry Run:** `pipenv run python ShokoBridge.py --dry-run --debug`

---

## Configuration (`config.json`)

* **`shoko.api_key`**: Generate this in the Shoko Web UI under **Settings -> API Keys**.
* **`tmdb.api_key`**: Get a free API key from themoviedb.org.
* **`directories`**: Use absolute paths. For Docker, these are the paths *inside the container*.
* **`destination_movies` (Optional):** Specify a separate destination for movie files. If this key is omitted, movies will be placed in a subfolder within the main `destination` directory.
* **`shoko.url` (for WSL users):** Use the special `http://windows.host:8111`. The script will resolve the IP automatically.
* **`link_type`**: Your choice of file operation.
    * `'move'`: **Moves** the original file.
    * `'copy'`: Creates a full duplicate of the file. Use this if linking fails and you want to keep your original file structure.
    * `'symlink'`: Creates a symbolic link. Recommended for network shares or different drives.
    * `'hardlink'`: Creates a hardlink. Most efficient for space, but source and destination must be on the same drive.
* **`path_mappings` & `use_relative_symlinks` (for advanced symlink setups):**
    * If your Plex server and this script see your media storage with different paths (e.g., `/mnt/z/` vs `/storage/`), use `path_mappings` to translate the path.
    * If you have issues with Plex not playing symlinked files, set `"use_relative_symlinks": true` and remove the `path_mappings` section.

---

## The Complete Workflow

1. **Setup:** Follow the installation steps above.
2. **Configure:** Fill out `config.json` with your details and correct paths.
3. **Dry Run:** Run the script with `--dry-run --debug` to verify its planned actions.
4. **Initial Run:** Run the script normally to build your Plex-ready library.
5. **Configure Plex:** Create a new "TV Shows" library and point it **only** to your `destination` directory. Ensure the agent is "Plex TV Series".
6. **Ongoing Maintenance:** Periodically run the script to add new files and `--cleanup` to remove old links. This can be automated with Task Scheduler (Windows) or Cron (Linux).
   * **If you configured `destination_movies`**, create a separate "Movies" library in Plex and point it to that path.
