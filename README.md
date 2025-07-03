# ShokoBridge

A robust, stateful automation script designed to bridge the gap between Shoko Server's AniDB-centric organization and Plex's media structure for both TV shows and movies. ShokoBridge creates a perfect, Plex-compatible library structure using your choice of file operations (move, copy, hardlink, or symlink), ensuring your anime library is beautifully organized and playable in any environment.

---

## The Problem It Solves

Shoko Server is the definitive tool for identifying and organizing anime based on the highly accurate AniDB database. However, AniDB uses an absolute episode numbering scheme (e.g., episode 1-201). Plex, on the other hand, relies on The Movie Database (TMDb) for its structure, which organizes shows into discrete seasons.

This creates a data model conflict, causing Plex's default scanner to fail on complex, long-running, or multi-part series, and to misclassify anime movies. This results in incorrectly merged shows, missing seasons, and a disorganized movie library.

**ShokoBridge** is the definitive solution. It acts as an intelligent integration layer:

1. It uses Shoko to reliably identify every file in your collection.
2. It leverages Shoko's built-in TMDb integration to get the official movie or season/episode structure for each file, minimizing external API calls.
3. It programmatically builds a perfect, Plex-compatible directory structure using your configured file operation method.
4. It maintains a stateful database to only process new files and includes robust cleanup and logging features.

The result is a fully automated, "set it and forget it" system for a perfect anime library in Plex, no matter how complex your setup.

## Features

* **External Configuration:** All settings are managed in an easy-to-edit `config.json` file.
* **Stateful Database:** Uses an SQLite database (`shokobridge_state.db`) to keep track of processed files.
* **Intelligent Matching:**
  * **Handles Movies & Shows:** Correctly identifies and separates anime movies from TV series.
  * **Optimized API Usage:** Leverages the rich TMDb data provided directly by the Shoko API to determine movie titles, season/episode numbers, and release dates, drastically reducing calls to the TMDb API.
  * **Robust Identification Hierarchy:** Uses TMDb Movie IDs first, then TMDb Episode IDs for perfect accuracy.
  * **Smart Fallbacks:** If a direct ID match isn't possible, it falls back to title similarity for regular episodes and uses AniDB types to correctly categorize extras (Specials, Trailers, etc.).
* **Flexible File Operations:**
  * **`move`**: Moves files to the destination.
  * **`copy`**: Duplicates files, ensuring maximum compatibility.
  * **`hardlink`**: Creates links that save space (source and destination must be on the same filesystem).
  * **`symlink`**: Creates symbolic links for cross-filesystem or network setups.
* **Advanced Pathing for Complex Setups:**
  * **`use_relative_symlinks`**: Creates relative symlinks to resolve playback issues in environments like Docker or WSL/NAS where paths differ between the script and Plex.
  * **`path_mappings`**: Translates the script's view of a path to the path Plex sees, providing a powerful solution for the "split-brain" problem.
* **Cross-Platform:** Works seamlessly on both Windows and Linux.
* **Safe Management:** Includes `--cleanup` and `--dry-run` flags for safe and predictable library management.
* **Robust Logging:** Creates daily rolling log files with a `--debug` flag for verbose troubleshooting.
* **API Caching & Reporting:** Caches TMDb results to minimize API calls and generates reports for any files it cannot map.

---

## 1. Prerequisites

* A running **Shoko Server** (v5.1+) with your anime collection scanned.
* **Python 3.8+** installed on the machine where you will run the script.
* If using `hardlink` mode, your source and destination folders must be on the same drive/partition.

---

## 2. Setup and Installation

### Step 2.1: Prepare Project Files
1. **Create a Folder:** Create a dedicated folder for the project (e.g., `C:\Scripts\ShokoBridge`).
2. **Save the Script:** Place the `ShokoBridge.py` script inside this folder.
3. **Create `config.json`:** In the same folder, create a file named `config.json`. Copy the template below into it.

**`config.json` Template:**
```json
{
    "shoko": {
        "url": "[http://windows.host:8111](http://windows.host:8111)",
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
