import logging
from datetime import datetime
from pathlib import Path
from typing import List

from models.movie_info import MovieInfo

logger = logging.getLogger(__name__)


def _format_size(num_bytes: int) -> str:
    """Render a byte count as a human-readable size string."""
    gigabytes = num_bytes / 1_000_000_000
    if gigabytes >= 1:
        return f"{gigabytes:.1f} GB"
    return f"{num_bytes / 1_000_000:.0f} MB"


def _plural(count: int) -> str:
    """Return an 's' suffix for counts other than one."""
    return "" if count == 1 else "s"


class SummaryWriter:
    """Renders and writes the human-readable expiring-soon digest (e.g. for MOTD)."""

    def __init__(self, summary_path: str, expiring_soon_days: int = 30):
        """Initialize the writer and ensure its directory exists.

        Args:
            summary_path: Path to the digest file.
            expiring_soon_days: Window, in days, described in the digest header.
        """
        self.path = Path(summary_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.expiring_soon_days = expiring_soon_days

    def write(
        self, upcoming: List[MovieInfo], deleted_count: int, bytes_freed: int, dry_run: bool
    ) -> None:
        """Render the digest and overwrite the summary file.

        Args:
            upcoming: Movies expiring within the configured window.
            deleted_count: Movies deleted (or that would be deleted) this run.
            bytes_freed: Disk space freed (or that would be freed) this run.
            dry_run: Whether this was a simulated run.
        """
        try:
            self.path.write_text(
                self._render(upcoming, deleted_count, bytes_freed, dry_run), encoding="utf-8"
            )
        except OSError as error:
            logger.error(f"Failed to write summary file {self.path}: {error}")

    def _render(
        self, upcoming: List[MovieInfo], deleted_count: int, bytes_freed: int, dry_run: bool
    ) -> str:
        """Build the digest text."""
        now = datetime.now()
        lines = [f"plex_cleaner — last run {now.strftime('%Y-%m-%d %H:%M')}"]

        if upcoming:
            lines.append(
                f"{len(upcoming)} movie{_plural(len(upcoming))} expiring "
                f"within {self.expiring_soon_days}d:"
            )
            for movie in sorted(upcoming, key=lambda item: item.expires_at):
                days_left = (movie.expires_at - now).days
                lines.append(f"  • {movie.title} — {movie.expires_at.strftime('%Y-%m-%d')} ({days_left}d)")
        else:
            lines.append(f"No movies expiring within {self.expiring_soon_days}d.")

        if dry_run:
            lines.append(
                f"Last run (dry-run): would delete {deleted_count}, ~{_format_size(bytes_freed)}."
            )
        else:
            lines.append(f"Last run: deleted {deleted_count}, freed {_format_size(bytes_freed)}.")

        return "\n".join(lines) + "\n"
