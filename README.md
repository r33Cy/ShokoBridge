# ShokoBridge

A robust, stateful automation script designed to bridge the gap between Shoko Server's AniDB-centric organization and Plex's media structure for both TV shows and movies. ShokoBridge creates a perfect, Plex-compatible library structure using your choice of file operations (move, copy, hardlink, or symlink), ensuring your anime library is beautifully organized and playable in any environment.

---

## The Problem It Solves

The official **Shoko Metadata** plugin was once the ideal way to integrate an anime library with Plex. However, support for legacy plugins and third-party scanners was officially removed, a change that fully impacted devices like the Nvidia Shield with Plex Media Server v1.41.0.8992.

This left the community without a direct integration method, creating a major problem:

*   **Plex's native scanner** requires TMDb-style naming (`Show/Season 01/S01E01.mkv`).
*   **Shoko's library** is organized by AniDB's absolute numbering.

This incompatibility means Plex cannot understand a raw Shoko library, leading to failed scans, incorrectly merged shows, and missing seasons—a problem especially felt on locked-down devices like the Nvidia Shield where alternative solutions are limited.

**ShokoBridge** is the definitive solution. It acts as an intelligent integration layer:

1. It uses Shoko to reliably identify every file in your collection.
2. It leverages Shoko's built-in TMDb integration to get the official movie or season/episode structure for each file, minimizing external API calls.
3. It programmatically builds a perfect, Plex-compatible directory structure that Plex's **native scanner can understand**, using your configured file operation method.
4. It maintains a stateful database to only process new files and includes robust cleanup and logging features.

The result is a fully automated, "set it and forget it" system for a perfect anime library in Plex, no matter how complex your setup.

## Features

* **External Configuration:** All settings are managed in an easy-to-edit `config.json` file.
* **Stateful Database:** Uses an SQLite database (`shokobridge_state.db`) to keep track of processed files.
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
* **Cross-Platform:** Works seamlessly on both Windows and Linux.

---

## 1. Prerequisites

*   A running **Shoko Server** (v5.1+) with your anime collection scanned.
*   **Docker** and **Docker Compose** installed on your system.
*   If using `hardlink` mode, your source and destination folders must be on the same drive/partition.

---

## 2. Setup and Installation

### Docker Setup (Recommended)

This is the easiest and most reliable way to run ShokoBridge.

1.  **Create a Project Folder:** Create a dedicated folder for your ShokoBridge configuration (e.g., `/opt/shokobridge` or `C:\Docker\Shokobridge`).

2.  **Create `config.json`:** Inside this new folder, create a `config.json` file. Copy the template below and fill it with your details.
    *   **IMPORTANT:** The `shoko.url` must be the actual IP address of your Shoko server (e.g., `http://192.168.1.100:8111`). Do not use `localhost` or `windows.host`.
    *   The `source_root`, `destination`, and `destination_movies` paths should be the paths *as they will be seen inside the container*. The example below uses `/anime`, `/plex-shows`, and `/plex-movies`.

    ```json
    {
        "shoko": {
            "url": "http://192.168.1.100:8111",
            "api_key": "YOUR_SHOKO_API_KEY"
        },
        "tmdb": {
            "api_key": "YOUR_TMDB_API_KEY"
        },
        "directories": {
            "source_root": "/anime",
            "destination": "/plex-shows",
            "destination_movies": "/plex-movies"
        },
        "options": {
            "link_type": "symlink"
        }
    }
    ```

3.  **Create `docker-compose.yml`:** In the same folder, create a `docker-compose.yml` file. Copy the example below and **edit the volume paths on the left** to match the locations on your host machine.

    ```yaml
    version: '3.8'
    services:
      shokobridge:
        image: r33cy/shokobridge:latest # Replace with your username if you build your own
        container_name: shokobridge
        volumes:
          # Mount your config file
          - ./config.json:/app/config.json:ro
          # Mount your host media paths to the container paths defined in config.json
          - /path/on/host/to/anime:/anime:ro
          - /path/on/host/to/plex-shows:/plex-shows
          - /path/on/host/to/plex-movies:/plex-movies
          # Mount persistent data and logs
          - ./data:/app
    ```

4.  **Run the Script:** Open a terminal in your project folder and use `docker-compose` to run the script.
    *   **Initial Run:** `docker-compose run --rm shokobridge`
    *   **Cleanup Run:** `docker-compose run --rm shokobridge --cleanup`
    *   **Dry Run:** `docker-compose run --rm shokobridge --dry-run --debug`

### Manual Setup (from Source)

Use this method if you cannot use Docker.

1.  **Prepare Project Files**
1. **Create a Folder:** Create a dedicated folder for the project (e.g., `C:\Scripts\ShokoBridge`).
2. **Save the Script:** Place the `ShokoBridge.py` script inside this folder.
3. **Create `config.json`:** In the same folder, create a file named `config.json`. Copy the template below into it.

**`config.json` Template:**
```json
{
    "shoko": {
        "url": "http://windows.host:8111",
        "api_key": "YOUR_SHOKO_API_KEY"
    },
    "tmdb": {
        "api_key": "YOUR_TMDB_API_KEY"
    },
    "directories": {
        "source_root": "/mnt/z/Media/Anime",
        "destination": "/mnt/z/Media/Plex-Anime-Shows",
        "destination_movies": "/mnt/z/Media/Plex-Anime-Movies"
    },
    "path_mappings": [
        {
            "script_path": "/mnt/z/",
            "plex_path": "/storage/0021-87E2/"
        }
    ],
    "options": {
        "language_priority": [
            "en",
            "x-jat"
        ],
        "link_type": "move",
        "use_relative_symlinks": false,
        "title_similarity_threshold": 0.8
    }
}
```

### Step 2.2: Install Dependencies
It is highly recommended to use a tool like `pipenv` to manage dependencies.

1.  **Install Management Tool (if needed):**
    ```bash
    # On Debian/Ubuntu using pipx (recommended)
    sudo apt update && sudo apt install pipx -y
    pipx ensurepath
    pipx install pipenv
    
    # On Windows using pipx (recommended)
    pip install pipx
    pipx ensurepath
    pipx install pipenv
    ```
    **Important:** Close and reopen your terminal after running `pipx ensurepath`.

2.  **Install `requests`:** Open a terminal in your project folder and run:
    ```bash
    pipenv install requests
    ```

### Step 2.3: Configure the `config.json` File
Open `config.json` and fill in your details.
* **`shoko.api_key`**: Generate this in the Shoko Web UI under **Settings -> API Keys**.
* **`tmdb.api_key`**: Get a free API key from [themoviedb.org](https://www.themoviedb.org).
* **`directories`**: Use absolute paths for the OS where the script will run.
    * *Windows Example:* `"source_root": "Z:\\Media\\Anime"` (use double backslashes)
    * *Linux/WSL Example:* `"source_root": "/mnt/z/Media/Anime"`
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

## 3. Usage

All commands should be run from inside your project folder. **Prefix commands with `pipenv run` if you used the Pipenv setup.**

* **Normal Run:** `pipenv run python ShokoBridge.py`
* **Cleanup Run:** `pipenv run python ShokoBridge.py --cleanup`
* **Dry Run & Debug:** `pipenv run python ShokoBridge.py --dry-run --debug`

---

## 4. The Complete Workflow

1. **Setup:** Follow the installation steps above.
2. **Configure:** Fill out `config.json` with your details and correct paths.
3. **Dry Run:** Run `pipenv run python ShokoBridge.py --dry-run --debug` to verify its planned actions.
4. **Initial Run:** Run `pipenv run python ShokoBridge.py` to build your Plex-ready library.
5. **Configure Plex:** Create a new "TV Shows" library and point it **only** to your `destination` directory. Ensure the agent is "Plex TV Series".
6. **Ongoing Maintenance:** Periodically run the script to add new files and `--cleanup` to remove old links. This can be automated with Task Scheduler (Windows) or Cron (Linux).
   * **If you configured `destination_movies`**, create a separate "Movies" library in Plex and point it to that path.
