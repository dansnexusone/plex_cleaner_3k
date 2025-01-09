from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .external_rating import ExternalRating


@dataclass
class MovieInfo:
    title: str
    tmdb_id: int
    radarr_id: int
    added_at: datetime
    external_ratings: ExternalRating
    requested_by: Optional[str]
    last_watched: Optional[datetime]
    user_rating: Optional[float]
    expires_at: Optional[datetime] = None
