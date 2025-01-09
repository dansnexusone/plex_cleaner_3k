from pathlib import Path

import yaml

from models.config import Config, DaysThreshold, RadarrConfig, RatingThreshold


class ConfigManager:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> Config:
        with open(self.config_path) as f:
            data = yaml.safe_load(f)

        return Config(
            plex_url=data["plex"]["url"],
            plex_token=data["plex"]["token"],
            tautulli_url=data["tautulli"]["url"],
            tautulli_api_key=data["tautulli"]["api_key"],
            radarr_uhd=RadarrConfig(
                url=data["radarr"]["4k"]["url"], api_key=data["radarr"]["4k"]["api_key"]
            ),
            radarr_streaming=RadarrConfig(
                url=data["radarr"]["1080p"]["url"], api_key=data["radarr"]["1080p"]["api_key"]
            ),
            overseerr_url=data["overseerr"]["url"],
            overseerr_api_key=data["overseerr"]["api_key"],
            overseerr_email=data["overseerr"]["email"],
            overseerr_password=data["overseerr"]["password"],
            admin_emails=data["admin_emails"],
            days_threshold=DaysThreshold(
                admin=data["deletion_threshold"]["days"]["users"]["admin"],
                user=data["deletion_threshold"]["days"]["users"]["user"],
                low_rating=data["deletion_threshold"]["days"]["rules"]["low_rated"],
            ),
            rating_threshold=RatingThreshold(
                admin=data["deletion_threshold"]["rating"]["users"]["admin"],
                user=data["deletion_threshold"]["rating"]["users"]["user"],
                low_rating=data["deletion_threshold"]["rating"]["rules"]["low"],
            ),
        )
