import logging
from datetime import datetime
from typing import List, Tuple

import requests

from models.config import NtfyConfig
from models.movie_info import MovieInfo

logger = logging.getLogger(__name__)


def _plural(count: int) -> str:
    """Return an 's' suffix for counts other than one."""
    return "" if count == 1 else "s"


class NtfyNotifier:
    """Pushes a run summary to ntfy when movies were deleted or are about to be."""

    def __init__(self, config: NtfyConfig):
        """Store config; sending is skipped later if disabled or unconfigured."""
        self.config = config

    def notify(
        self, deleted: List[MovieInfo], imminent: List[MovieInfo], dry_run: bool
    ) -> None:
        """Send a notification about this run, or stay silent when nothing warrants one.

        A message goes out only when the notifier is enabled and configured, and
        there is something to report — movies deleted this run, or movies within
        the configured window of deletion. Quiet runs send nothing.

        Args:
            deleted: Movies deleted this run (or that would be, on a dry run).
            imminent: Movies within `notify_within_days` of deletion.
            dry_run: Whether deletions were simulated rather than performed.
        """
        if not self.config.enabled or not self.config.topic:
            return

        if not deleted and not imminent:
            return

        title, message = self._compose(deleted, imminent, dry_run)

        try:
            requests.post(
                f"{self.config.server.rstrip('/')}/{self.config.topic}",
                data=message.encode("utf-8"),
                headers={
                    "Title": title,
                    "Priority": self.config.priority,
                    "Tags": "wastebasket",
                },
                timeout=10,
            )
        except requests.RequestException as error:
            logger.error(f"Failed to send ntfy notification: {error}")

    def _compose(
        self, deleted: List[MovieInfo], imminent: List[MovieInfo], dry_run: bool
    ) -> Tuple[str, str]:
        """Build the notification title and body from this run's outcome."""
        verb = "Would delete" if dry_run else "Deleted"

        title_parts = []
        if deleted:
            title_parts.append(f"{verb.lower()} {len(deleted)}")
        if imminent:
            title_parts.append(f"{len(imminent)} expiring soon")
        title = "Plex Cleaner: " + ", ".join(title_parts)

        lines = []
        if deleted:
            lines.append(f"{verb} {len(deleted)} movie{_plural(len(deleted))}:")
            lines += [f"- {movie.title}" for movie in deleted]
        if imminent:
            if lines:
                lines.append("")
            now = datetime.now()
            lines.append(f"Expiring within {self.config.notify_within_days}d:")
            for movie in sorted(imminent, key=lambda item: item.expires_at):
                days_left = (movie.expires_at - now).days
                lines.append(f"- {movie.title} ({days_left}d)")

        return title, "\n".join(lines)
