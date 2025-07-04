# shokobridge/file_manager.py
import logging
import os
import shutil

class FileManager:
    """Handles all filesystem operations like linking, moving, and cleaning up files."""

    def __init__(self, config, dry_run=False):
        """
        Initializes the FileManager.

        :param config: The configuration dictionary.
        :param dry_run: If True, no changes will be made to the filesystem.
        """
        self.config = config
        self.dry_run = dry_run
        self.link_type = config['options'].get('link_type', 'symlink')
        logging.debug("FileManager initialized (Dry Run: %s, Link Type: %s)", self.dry_run, self.link_type)

    def find_supplemental_files(self, media_file_path, dir_cache):
        """Finds supplemental files using a directory cache to avoid redundant I/O."""
        if not os.path.exists(media_file_path):
            return []

        supplemental_files = []
        source_dir = os.path.dirname(media_file_path)
        media_file_name = os.path.basename(media_file_path)
        media_basename, _ = os.path.splitext(media_file_name)

        if source_dir not in dir_cache:
            try:
                logging.debug("  Caching directory contents for: %s", source_dir)
                dir_cache[source_dir] = os.listdir(source_dir)
            except OSError as e:
                logging.error("  Could not scan for supplemental files in %s. Error: %s", source_dir, e)
                dir_cache[source_dir] = []

        file_list = dir_cache.get(source_dir, [])
        for filename in file_list:
            if filename.startswith(media_basename) and filename != media_file_name:
                supplemental_ext = filename[len(media_basename):]
                full_path = os.path.join(source_dir, filename)
                supplemental_files.append((full_path, supplemental_ext))
                
        if supplemental_files:
            logging.info("  Found %d supplemental file(s) for '%s'.", len(supplemental_files), os.path.basename(media_file_path))
        return supplemental_files

    def process_file_group(self, source_file_path, destination_file_path, dir_cache):
        """
        Processes a media file and its supplemental files as a single transaction.
        Returns True if the entire group was processed successfully.
        """
        files_to_process = [(source_file_path, destination_file_path)]
        supplemental_files = self.find_supplemental_files(source_file_path, dir_cache)
        
        dest_base_name, _ = os.path.splitext(destination_file_path)
        for supp_source_path, supp_ext in supplemental_files:
            supp_dest_path = f"{dest_base_name}{supp_ext}"
            files_to_process.append((supp_source_path, supp_dest_path))

        all_successful = True
        successfully_linked_paths = []
        for src_path, dest_path in files_to_process:
            if self._link_single_file(src_path, dest_path):
                if not self.dry_run:
                    successfully_linked_paths.append(dest_path)
            else:
                all_successful = False
                logging.error("  ! FAILED to process a file in the group for '%s'. Rolling back changes for this group.", os.path.basename(source_file_path))
                if not self.dry_run:
                    for path_to_remove in successfully_linked_paths:
                        try:
                            if os.path.exists(path_to_remove):
                                os.remove(path_to_remove)
                                logging.info("    - ROLLED BACK (deleted): %s", os.path.basename(path_to_remove))
                        except Exception as e:
                            logging.error("    - FAILED to roll back %s. Error: %s", os.path.basename(path_to_remove), e)
                break
        
        return all_successful

    def cleanup_stale_files(self, dest_path):
        """Removes a stale file and its supplemental files."""
        dest_dir = os.path.dirname(dest_path)
        if not os.path.exists(dest_dir):
            logging.warning("  > Destination directory not found: %s. Nothing to remove.", dest_dir)
            return

        dest_basename, _ = os.path.splitext(os.path.basename(dest_path))
        files_in_dir = os.listdir(dest_dir)
        files_to_remove = [f for f in files_in_dir if f.startswith(dest_basename)]
        
        if not files_to_remove:
            logging.warning("  > Link path not found for base '%s'.", dest_basename)
            return
        
        for filename in files_to_remove:
            full_path = os.path.join(dest_dir, filename)
            if self.dry_run:
                logging.info("  [DRY RUN] Would delete stale file: %s", full_path)
            elif os.path.exists(full_path):
                try:
                    os.remove(full_path)
                    logging.info("  > Link successfully removed: %s", filename)
                except OSError as e:
                    logging.error("  > FAILED to remove stale file %s. Error: %s", full_path, e)

    def cleanup_empty_dirs(self, root_dir):
        """Removes empty directories in the given root directory."""
        if self.dry_run:
            logging.info("[DRY RUN] Skipping cleanup of empty directories.")
            return
        
        logging.info("Cleaning up empty directories in destination...")
        for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
            if not dirnames and not filenames:
                try:
                    os.rmdir(dirpath)
                    logging.debug("  > Removed empty directory: %s", dirpath)
                except OSError as e:
                    logging.error("  > FAILED to remove empty directory %s. Error: %s", dirpath, e)

    def _link_single_file(self, source_path, dest_path):
        """Handles the file operation for a single file."""
        logging.debug("    Processing link for: '%s'", os.path.basename(source_path))
        logging.debug("      Source: %s", source_path)
        logging.debug("      Destination: %s", dest_path)

        if os.path.exists(dest_path):
            logging.debug("    Destination already exists, skipping: %s", os.path.basename(dest_path))
            return True

        if self.dry_run:
            # In dry run, still log the symlink path calculation for clarity
            if self.link_type == 'symlink':
                self._calculate_symlink_target(source_path, dest_path)
            logging.info("    [DRY RUN] Would %s '%s' to '%s'", self.link_type, os.path.basename(source_path), os.path.basename(dest_path))
            return True

        try:
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            if self.link_type == 'copy':
                shutil.copy2(source_path, dest_path)
            elif self.link_type == 'hardlink':
                os.link(source_path, dest_path)
            elif self.link_type == 'move':
                shutil.move(source_path, dest_path)
            else: # symlink
                symlink_target = self._calculate_symlink_target(source_path, dest_path)
                os.symlink(symlink_target, dest_path)
            logging.info("    + %s: %s", self.link_type.upper(), os.path.basename(dest_path))
            return True
        except Exception as e:
            logging.error("    - FAILED to %s '%s'. Error: %s", self.link_type, os.path.basename(source_path), e)
            return False

    def _calculate_symlink_target(self, source_path, dest_path):
        """Calculates the correct target path for a symlink based on config options."""
        # Path mappings should take precedence over relative symlinks.
        # A mapped path is always absolute from Plex's perspective.
        if self.config.get('path_mappings'):
            for mapping in self.config['path_mappings']:
                script_path = mapping.get('script_path')
                plex_path = mapping.get('plex_path')
                if script_path and plex_path and source_path.startswith(script_path):
                    mapped_path = source_path.replace(script_path, plex_path, 1)
                    logging.debug("      Applied path mapping: '%s' -> '%s'", script_path, plex_path)
                    logging.debug("      Plex-visible Symlink Target: %s", mapped_path)
                    return mapped_path

        # If no path mapping was applied, check for relative symlink option.
        if self.config['options'].get('use_relative_symlinks', False):
            relative_path = os.path.relpath(source_path, start=os.path.dirname(dest_path))
            logging.debug("      Calculated relative symlink target.")
            logging.debug("      Plex-visible Symlink Target: %s", relative_path)
            return relative_path

        # Default to absolute source path.
        logging.debug("      Plex-visible Symlink Target: %s", source_path)
        return source_path