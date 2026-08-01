import logging
import platform
import requests
from typing import Optional

from qtpy.QtCore import QThread, Signal

from src import __version__
from src.utils.version import is_newer_version

log = logging.getLogger("sound_processor.utils.updater")

REPO_URL = "https://api.github.com/repos/Josh682/sopro_studio/releases"


class UpdateCheckerWorker(QThread):
    """Background worker to check for application updates via GitHub API.
    
    Fails silently on network errors or rate limits to avoid annoying the user.
    """
    
    # Emits (version_string, release_notes, download_url)
    update_available = Signal(str, str, str)

    def __init__(self, include_prerelease: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.include_prerelease = include_prerelease

    def run(self) -> None:
        try:
            log.debug("Checking for updates...")
            response = requests.get(
                REPO_URL,
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=(3.0, 5.0)  # (connect timeout, read timeout)
            )
            
            # Silent failure for rate limits or server errors
            if response.status_code != 200:
                log.warning("Update check failed with status %d", response.status_code)
                return
                
            releases = response.json()
            if not releases:
                log.debug("No releases found on GitHub.")
                return
                
            # Find the latest valid release
            latest_release = None
            for release in releases:
                if release.get("draft", False):
                    continue
                if release.get("prerelease", False) and not self.include_prerelease:
                    continue
                latest_release = release
                break
                
            if not latest_release:
                log.debug("No valid release found after filtering drafts/prereleases.")
                return
                
            tag_name = latest_release.get("tag_name", "")
            
            if is_newer_version(__version__, tag_name):
                log.info("New version %s is available (current: %s)", tag_name, __version__)
                
                # Format release notes
                body = latest_release.get("body", "No release notes provided.")
                # Keep it concise: first 10 lines max
                lines = body.strip().split("\n")
                if len(lines) > 10:
                    notes = "\n".join(lines[:10]) + "\n\n..."
                else:
                    notes = body
                    
                # Find appropriate download URL based on platform
                download_url = self._get_asset_download_url(latest_release)
                
                self.update_available.emit(tag_name, notes, download_url)
            else:
                log.debug("App is up to date.")
                
        except requests.RequestException as e:
            # Silent failure for network issues, offline mode, timeouts
            log.warning("Update check failed due to network error: %s", e)
        except Exception as e:
            log.error("Unexpected error during update check: %s", e)

    def _get_asset_download_url(self, release: dict) -> str:
        """Find the most appropriate asset download URL for the current OS."""
        system = platform.system().lower()
        assets = release.get("assets", [])
        
        fallback_url = release.get("html_url", "")
        
        for asset in assets:
            name = asset.get("name", "").lower()
            url = asset.get("browser_download_url", fallback_url)
            
            if system == "darwin" and name.endswith(".dmg"):
                return url
            if system == "windows" and name.endswith(".exe"):
                return url
            if system == "linux" and name.endswith(".AppImage"):
                return url
                
        return fallback_url
