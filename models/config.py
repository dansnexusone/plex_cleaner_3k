from dataclasses import dataclass, field
from typing import List


@dataclass
class PlexConfig:
    url: str
    token: str


@dataclass
class TautulliConfig:
    url: str
    api_key: str


@dataclass
class SonarrConfig:
    url: str
    api_key: str


@dataclass
class RadarrConfig:
    url: str
    api_key: str
    name: str = ""


@dataclass
class DaysThreshold:
    admin: int
    user: int
    low_rating: int
    mid: int


@dataclass
class RatingThreshold:
    admin: int
    user: int
    low_rating: int


@dataclass
class OverseerrConfig:
    url: str
    api_key: str
    email: str
    password: str
    admin_emails: list[str] = field(default_factory=list)


@dataclass
class AuditConfig:
    log_path: str
    summary_path: str
    expiring_soon_days: int = 30


@dataclass
class Config:
    plex: PlexConfig
    tautulli: TautulliConfig
    radarr: List[RadarrConfig]
    overseerr: OverseerrConfig
    days_threshold: DaysThreshold
    rating_threshold: RatingThreshold
    audit: AuditConfig
    admin_emails: list[str] = field(default_factory=list)
