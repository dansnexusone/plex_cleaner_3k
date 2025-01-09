from dataclasses import dataclass
from typing import Optional


@dataclass
class ExternalRating:
    imdb: Optional[float]
    rotten_tomatoes: Optional[float]
    tmdb: Optional[float]
    metacritic: Optional[float]
    trakt: Optional[float]
