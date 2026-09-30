import os
import random
from wallpaper_engine import SUPPORTED_EXTENSIONS


class PlaylistManager:
    """
    Manages image discovery across multiple folders, random shuffle queues,
    and history tracking for previous/next navigation.
    """

    def __init__(self, folders=None, include_subfolders=True, history=None):
        self.folders = list(folders or [])
        self.include_subfolders = include_subfolders
        self.all_images = []
        self.folder_counts = {}
        self.shuffle_queue = []
        self.history = list(history or [])
        self.history_index = len(self.history) - 1 if self.history else -1
        self.current_image = self.history[-1] if self.history else None

        self.rescan()

    def set_folders(self, folders: list):
        self.folders = list(folders)
        self.rescan()

    def set_include_subfolders(self, include_subfolders: bool):
        if self.include_subfolders != include_subfolders:
            self.include_subfolders = include_subfolders
            self.rescan()

    def add_folder(self, folder_path: str) -> bool:
        norm_path = os.path.normpath(folder_path)
        if norm_path not in [os.path.normpath(f) for f in self.folders]:
            self.folders.append(norm_path)
            self.rescan()
            return True
        return False

    def remove_folder(self, folder_path: str) -> bool:
        norm_path = os.path.normpath(folder_path)
        orig_len = len(self.folders)
        self.folders = [f for f in self.folders if os.path.normpath(f) != norm_path]
        if len(self.folders) != orig_len:
            self.rescan()
            return True
        return False

    def rescan(self):
        """Scans all configured folders and updates image pool and shuffle queue."""
        found_images = []
        self.folder_counts = {}

        for folder in self.folders:
            if not os.path.isdir(folder):
                self.folder_counts[folder] = 0
                continue

            count = 0
            if self.include_subfolders:
                for root, _, files in os.walk(folder):
                    for file in files:
                        ext = os.path.splitext(file)[1].lower()
                        if ext in SUPPORTED_EXTENSIONS:
                            full_path = os.path.join(root, file)
                            found_images.append(full_path)
                            count += 1
            else:
                try:
                    for entry in os.scandir(folder):
                        if entry.is_file():
                            ext = os.path.splitext(entry.name)[1].lower()
                            if ext in SUPPORTED_EXTENSIONS:
                                found_images.append(entry.path)
                                count += 1
                except Exception as e:
                    print(f"Error scanning folder {folder}: {e}")

            self.folder_counts[folder] = count

        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for img in found_images:
            norm = os.path.normcase(os.path.normpath(img))
            if norm not in seen:
                seen.add(norm)
                deduped.append(img)

        self.all_images = deduped

        # Rebuild shuffle queue
        self._rebuild_shuffle_queue()

    def _rebuild_shuffle_queue(self):
        """Creates a newly randomized queue of all available images."""
        if not self.all_images:
            self.shuffle_queue = []
            return

        queue = list(self.all_images)
        random.shuffle(queue)

        # Avoid having the first image of the new queue be the current image
        if len(queue) > 1 and self.current_image and queue[0] == self.current_image:
            queue[0], queue[-1] = queue[-1], queue[0]

        self.shuffle_queue = queue

    def get_total_count(self) -> int:
        return len(self.all_images)

    def get_folder_counts(self) -> dict:
        return self.folder_counts

    def get_next_wallpaper(self) -> str:
        """
        Picks the next wallpaper. If navigating forward from history, steps forward.
        Otherwise pulls the next item from the shuffle queue.
        """
        # If user stepped backwards into history and is now clicking Next
        if 0 <= self.history_index < len(self.history) - 1:
            self.history_index += 1
            candidate = self.history[self.history_index]
            if os.path.exists(candidate):
                self.current_image = candidate
                return candidate

        # Pull from shuffle queue
        while True:
            if not self.shuffle_queue:
                self._rebuild_shuffle_queue()
                if not self.shuffle_queue:
                    return ""

            candidate = self.shuffle_queue.pop(0)
            if os.path.exists(candidate):
                self.current_image = candidate
                # Add to history
                if not self.history or self.history[-1] != candidate:
                    self.history.append(candidate)
                    if len(self.history) > 50:
                        self.history.pop(0)
                self.history_index = len(self.history) - 1
                return candidate
            else:
                # File no longer exists, remove from all_images and retry
                if candidate in self.all_images:
                    self.all_images.remove(candidate)

    def get_previous_wallpaper(self) -> str:
        """Navigates back to the previous wallpaper in history."""
        if not self.history or self.history_index <= 0:
            return ""

        while self.history_index > 0:
            self.history_index -= 1
            candidate = self.history[self.history_index]
            if os.path.exists(candidate):
                self.current_image = candidate
                return candidate

        return ""

    def has_previous(self) -> bool:
        return self.history_index > 0

    def has_images(self) -> bool:
        return len(self.all_images) > 0
