from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from .external_rating import ExternalRating


@dataclass
class EpisodeInfo:
    """Information about a TV episode."""

    season_number: int
    episode_number: int
    title: str
    air_date: Optional[datetime]
    file_size: Optional[int]
    quality: Optional[str]
    last_watched: Optional[datetime]


@dataclass
class SeriesInfo:
    """Information about a TV series."""

    title: str
    tvdb_id: int
    sonarr_id: int
    added_at: datetime
    external_ratings: ExternalRating
    requested_by: Optional[str]
    last_watched: Optional[datetime]
    user_rating: Optional[float]
    episodes: List[EpisodeInfo]
    total_size: int
    monitored: bool
    status: str  # ended, continuing, upcoming
    network: Optional[str]
    expires_at: Optional[datetime] = None
