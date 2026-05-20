import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from models.movie_info import MovieInfo
from models.retention_decision import RetentionDecision

logger = logging.getLogger(__name__)


def _json_default(value: Any) -> str:
    """Serialize datetimes (and any other unknown types) for JSON output."""
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _format_date(value: Optional[datetime]) -> Optional[str]:
    """Render a datetime as a YYYY-MM-DD string, or None when absent."""
    return value.strftime("%Y-%m-%d") if value else None


class AuditLog:
    """Append-only JSONL record of deletion and expiry decisions."""

    def __init__(self, log_path: str, run_id: Optional[str] = None):
        """Initialize the audit log and ensure its directory exists.

        Args:
            log_path: Path to the JSONL file. Parent directories are created
                if missing.
            run_id: Identifier shared by every event in a single run. Defaults
                to the current timestamp.
        """
        self.path = Path(log_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id or datetime.now().isoformat(timespec="seconds")

    def record_deletion(
        self,
        movie_info: MovieInfo,
        decision: RetentionDecision,
        instances: List[str],
        size_freed_bytes: int,
        dry_run: bool,
    ) -> None:
        """Record a movie deletion, or a simulated one when dry_run is True.

        Args:
            movie_info: The movie that was (or would be) deleted.
            decision: The retention decision that scheduled it for deletion.
            instances: Names of the Radarr instances it was removed from.
            size_freed_bytes: Disk space reclaimed across those instances.
            dry_run: Whether the deletion was simulated.
        """
        self._append(
            {
                "action": "would_delete" if dry_run else "deleted",
                "dry_run": dry_run,
                "instances": instances,
                "size_freed_bytes": size_freed_bytes,
                **self._movie_fields(movie_info, decision),
            }
        )

    def record_expiring(self, movie_info: MovieInfo, decision: RetentionDecision) -> None:
        """Record a movie that will expire soon but is not yet deleted.

        Args:
            movie_info: The movie approaching expiry.
            decision: The retention decision describing its expiry.
        """
        self._append(
            {
                "action": "expiring_soon",
                "dry_run": False,
                **self._movie_fields(movie_info, decision),
            }
        )

    def _movie_fields(self, movie_info: MovieInfo, decision: RetentionDecision) -> Dict[str, Any]:
        """Build the movie and decision fields shared by every event."""
        return {
            "title": movie_info.title,
            "tmdb_id": int(movie_info.tmdb_id),
            "expires_at": _format_date(decision.expires_at),
            "reason": decision.reason.value,
            "retention_days": decision.retention_days,
            "inputs": decision.inputs,
        }

    def _append(self, event: Dict[str, Any]) -> None:
        """Append a single event to the log as one JSON line."""
        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "run_id": self.run_id,
            **event,
        }
        try:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, default=_json_default) + "\n")
        except OSError as error:
            logger.error(f"Failed to write audit event for {event.get('title')}: {error}")
