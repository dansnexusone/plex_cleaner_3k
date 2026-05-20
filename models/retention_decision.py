from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class RetentionReason(str, Enum):
    """Reason codes explaining why a movie is protected, retained, or expiring."""

    PROTECTED_USER_RATING = "protected_user_rating"
    PROTECTED_IMDB_TOP_250 = "protected_imdb_top_250"
    PROTECTED_HIGH_EXTERNAL_RATING = "protected_high_external_rating"
    LOW_USER_RATING = "low_user_rating"
    MEH_USER_RATING = "meh_user_rating"
    UNRATED_ADMIN = "unrated_admin"
    UNRATED_USER = "unrated_user"


@dataclass
class RetentionDecision:
    """Outcome of evaluating a movie against the retention policy.

    Attributes:
        reason: The dominant reason code that drove the outcome.
        expires_at: When the movie expires, or None if it is protected.
        retention_days: Days granted from the last activity date, or None when
            the movie is protected.
        inputs: Snapshot of the signals that drove the decision, retained for
            auditing.
    """

    reason: RetentionReason
    expires_at: Optional[datetime]
    retention_days: Optional[int]
    inputs: Dict[str, Any] = field(default_factory=dict)

    @property
    def protected(self) -> bool:
        """Whether the movie is protected from deletion (never expires)."""
        return self.expires_at is None
