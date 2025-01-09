from dataclasses import dataclass, field


@dataclass
class RadarrConfig:
    url: str
    api_key: str


@dataclass
class DaysThreshold:
    admin: int
    user: int
    low_rating: int


@dataclass
class RatingThreshold:
    admin: int
    user: int
    low_rating: int


@dataclass
class Config:
    plex_url: str
    plex_token: str
    tautulli_url: str
    tautulli_api_key: str
    radarr_uhd: RadarrConfig
    radarr_streaming: RadarrConfig
    overseerr_url: str
    overseerr_api_key: str
    overseerr_email: str
    overseerr_password: str
    days_threshold: DaysThreshold
    rating_threshold: RatingThreshold
    admin_emails: list[str] = field(default_factory=list)
