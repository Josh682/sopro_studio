import logging
from typing import Optional

from packaging.version import Version, InvalidVersion

log = logging.getLogger("sound_processor.utils.version")

def parse_github_tag(tag: str) -> Optional[Version]:
    """Parse a GitHub release tag (e.g., 'v1.2.3' or '1.2.3') into a semantic Version.
    
    Returns None if the tag is malformed.
    """
    # Remove leading 'v' or 'V'
    clean_tag = tag.strip().lstrip('vV')
    try:
        return Version(clean_tag)
    except InvalidVersion:
        log.warning("Invalid version format: %s", tag)
        return None

def is_newer_version(current_ver: str, remote_tag: str) -> bool:
    """Compare a current version string against a remote GitHub tag.
    
    Returns True if remote_tag represents a strictly newer semantic version.
    """
    current = parse_github_tag(current_ver)
    remote = parse_github_tag(remote_tag)
    
    if current is None or remote is None:
        return False
        
    return remote > current
