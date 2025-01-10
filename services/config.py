import os
from pathlib import Path

import dotenv
import yaml

from models.config import (
    Config,
    DaysThreshold,
    OverseerrConfig,
    PlexConfig,
    RadarrConfig,
    RatingThreshold,
    TautulliConfig,
)


class ConfigManager:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)

        # Load .env
        dotenv.load_dotenv()

        # Load config.yaml
        self.config = self._load_config()

    def _find_radarr_instances(self) -> tuple[str]:
        """
        Find configured Radarr instances from environment variables.

        Looks for RADARR_INSTANCES environment variable containing comma-separated
        instance names (e.g. "4k,1080p"). For each instance found, prepends "radarr_"
        to create the full instance name.

        Returns:
            tuple[str]: Tuple of Radarr instance names. If no instances are configured,
                       returns tuple containing just "radarr".
        """
        radarr_instances = []
        if os.getenv("RADARR_INSTANCES"):
            for instance in os.getenv("RADARR_INSTANCES").split(","):
                radarr_instances.append(f"radarr_{instance}")

        return tuple(radarr_instances if radarr_instances else ["radarr"])

    def _load_config(self) -> Config:
        """
        Load and parse configuration from config.yaml and environment variables.

        This method reads the config.yaml file and merges it with environment variables.
        Environment variables take precedence over config file values.

        The following configurations are loaded:
        - Plex server details (URL and token)
        - Tautulli details (URL and API key)
        - Radarr instances (URLs and API keys for 4K and 1080p)
        - Overseerr details (URL, API key, email, password)
        - Admin email addresses
        - Deletion thresholds for days and ratings

        Returns:
            Config: A Config object containing all parsed configuration values
        """
        with open(self.config_path) as f:
            data = yaml.safe_load(f)

            for key in ("plex", "tautulli", "overseerr") + self._find_radarr_instances():
                for field in ["url", "api_key" if key != "plex" else "token"] + (
                    ["email", "password", "admin_emails"] if key == "overseerr" else []
                ):
                    if os.getenv(f"{key.upper()}_{field.upper()}"):
                        data.setdefault(key, {})
                        data[key][field] = os.getenv(f"{key.upper()}_{field.upper()}")

        return Config(
            plex=PlexConfig(
                url=data["plex"]["url"],
                token=data["plex"]["token"],
            ),
            tautulli=TautulliConfig(
                url=data["tautulli"]["url"],
                api_key=data["tautulli"]["api_key"],
            ),
            radarr_uhd=RadarrConfig(
                url=data["radarr_4k"]["url"], api_key=data["radarr_4k"]["api_key"]
            ),
            radarr_streaming=RadarrConfig(
                url=data["radarr_1080p"]["url"], api_key=data["radarr_1080p"]["api_key"]
            ),
            overseerr=OverseerrConfig(
                url=data["overseerr"]["url"],
                api_key=data["overseerr"]["api_key"],
                email=data["overseerr"]["email"],
                password=data["overseerr"]["password"],
                admin_emails=data["overseerr"]["admin_emails"],
            ),
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
