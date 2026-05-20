import functools
import html
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests
import urllib3
from bs4 import BeautifulSoup
from plexapi.exceptions import NotFound
from plexapi.server import PlexServer
from tqdm import tqdm

from models.external_rating import ExternalRating
from models.movie_info import MovieInfo
from models.retention_decision import RetentionDecision, RetentionReason
from services.audit import AuditLog
from services.config import ConfigManager
from services.overseerr import OverseerrService
from services.radarr import RadarrService
from services.summary import SummaryWriter
from services.tautulli import TautulliService

logger = logging.getLogger(__name__)

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class MovieCleaner:
    """Manages the cleanup of movies from Radarr and Plex based on watch history and ratings."""

    def __init__(self):
        """Initialize MovieCleaner with necessary service connections."""
        self.config = ConfigManager().config

        # Set up Plex First
        self.plex = PlexServer(self.config.plex.url, self.config.plex.token)

        # Set up Radarr Instances
        self.radarr_instances = [RadarrService(instance) for instance in self.config.radarr]

        # Set up Tautulli
        self.tautulli = TautulliService(self.config.tautulli)

        # Set up Overseerr
        self.overseerr = OverseerrService(self.config.overseerr)

        # Set up the audit trail and human-readable summary
        self.audit = AuditLog(self.config.audit.log_path)
        self.summary = SummaryWriter(
            self.config.audit.summary_path, self.config.audit.expiring_soon_days
        )

        self.overseerr_requests = self.overseerr.get_all_requests()
        self.imdb_top_250 = self.scrape_imdb_top_250()

        self.combined_movies = self.get_combined_movies()
        self.upcoming_movies = []

    def get_combined_movies(self) -> dict[str, list[dict]]:
        """Get combined movie data from all configured Radarr instances.

        This method fetches movies from all configured Radarr instances and combines them
        into a single dictionary keyed by TMDB ID. Only movies that have associated files
        are included in the results.

        Each movie entry is augmented with its source Radarr instance to enable operations
        like deletion to be performed on the correct instance.

        Returns:
            dict[str, list[dict]]: A dictionary where:
                - key (str): TMDB ID of the movie
                - value (list[dict]): List of movie dictionaries containing:
                    - All original movie data from Radarr
                    - An 'instance' field containing the RadarrService instance

        Example structure:
            {
                "12345": [
                    {"instance": <RadarrService>, "tmdbId": 12345, "title": "Movie 1", ...},
                    {"instance": <RadarrService>, "tmdbId": 12345, "title": "Movie 1", ...}
                ]
            }
        """
        combined_movies = {}
        for instance in self.radarr_instances:
            movies = instance.get_movies()
            for movie in movies:
                if not movie["hasFile"]:
                    continue

                movie = {"instance": instance, **movie}

                tmdbid = str(movie["tmdbId"])
                if tmdbid not in combined_movies:
                    combined_movies[tmdbid] = [movie]
                else:
                    combined_movies[tmdbid].append(movie)

        return combined_movies

    def get_external_ratings(self, radarr_movie: dict) -> ExternalRating:
        """Get external ratings for a movie from TMDB."""
        ratings = {
            "imdb": None,
            "rotten_tomatoes": None,
            "tmdb": None,
            "metacritic": None,
            "trakt": None,
        }

        for service in ratings.keys():
            ratings[service] = (
                radarr_movie["ratings"].get(service.replace("_t", "T"), {}).get("value", None)
            )

            if ratings[service] and service in ["rotten_tomatoes", "metacritic"]:
                ratings[service] = ratings[service] / 10

        return ExternalRating(**ratings)

    def clean_movies(self, dry_run: bool = False) -> None:
        """
        Execute the movie cleanup process.

        Args:
            dry_run: If True, simulate the cleanup without actually deleting files
        """
        logger.info(f"Starting movie cleanup process... ({'DRY RUN' if dry_run else 'LIVE RUN'})")

        logger.info(f"Found {len(self.combined_movies)} movies to review from Radarr.")
        movies_to_delete = self._process_movies()

        self._record_expiring()
        self._log_statistics(movies_to_delete, len(self.combined_movies))

        bytes_freed = self._delete_movies(movies_to_delete, dry_run)
        self.summary.write(self.upcoming_movies, len(movies_to_delete), bytes_freed, dry_run)

    def _process_movies(self) -> List[MovieInfo]:
        """Process the list of Radarr movies in parallel."""

        # Partial function to avoid passing self and overseerr_requests repeatedly
        process_func = functools.partial(self._process_single_movie)

        # Process movies in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(
                tqdm(
                    executor.map(process_func, self.combined_movies.items()),
                    total=len(self.combined_movies),
                    desc="Processing Movies",
                    unit="movies",
                    leave=False,
                )
            )

        # Keep only the movies that should be deleted
        return [movie_info for movie_info in results if movie_info]

    def _process_single_movie(self, movie_item: Tuple[str, List[dict]]) -> Optional[MovieInfo]:
        """Process a single movie and determine if it should be deleted.

        This method takes a movie item tuple containing the TMDb ID and movie data,
        retrieves additional movie information, and evaluates whether the movie
        should be deleted based on configured criteria.

        Args:
            movie_item: A tuple containing:
                - TMDb ID (str): The TMDb ID of the movie
                - movie (list): List of movie data dictionaries from Radarr

        Returns:
            Optional[MovieInfo]: The MovieInfo (carrying its retention decision) if the
                movie should be deleted, None if it should be kept or an error occurred.

        Raises:
            NotFound: If the movie cannot be found when retrieving additional info
            Exception: For any other errors that occur during processing
        """
        tmdb_id, movie = movie_item

        if not tmdb_id:
            return None

        try:
            movie_info = self._get_movie_info(movie[0], tmdb_id)
            if self._should_delete_movie(movie_info):
                return movie_info
        except NotFound:
            pass
        except Exception as e:
            logger.error(f"Error processing movie {movie[0].get('title')}: {e}")

        return None

    def _determine_average_external_rating(self, movie_info: MovieInfo) -> Optional[float]:
        """Determine the average external rating for a movie, or None if it has none."""
        ratings = [
            value
            for field in fields(movie_info.external_ratings)
            if (value := getattr(movie_info.external_ratings, field.name))
        ]

        if not ratings:
            return None

        return round(sum(ratings) / len(ratings), 1)

    def scrape_imdb_top_250(self) -> List[str]:
        """
        Scrape the IMDB Top 250 list and return the titles.
        """

        try:
            # Get the IMDB Top 250 page
            response = requests.get(
                "https://www.imdb.com/chart/top",
                headers={
                    "User-Agent": "Mozilla/5.0",
                },
                verify=False,
            )
            response.raise_for_status()

            # Parse the HTML
            soup = BeautifulSoup(response.text, "html.parser")

            # Find all movie titles in the Top 250
            top_250 = json.loads(
                "".join(soup.find("script", {"type": "application/ld+json"}).contents)
            )

            return [html.unescape(x["item"]["name"]) for x in top_250["itemListElement"]]

        except Exception as e:
            logger.error(f"Error retrieving IMDB Top 250: {e}")
            return []

    def _is_imdb_top_250(self, movie_info: MovieInfo) -> bool:
        """
        Check if a movie is currently in the IMDB Top 250 list by scraping the IMDB website.

        Args:
            movie_info: MovieInfo object containing movie details

        Returns:
            bool: True if movie is in IMDB Top 250, False otherwise
        """

        return movie_info.title in self.imdb_top_250

    def _decision_inputs(self, movie_info: MovieInfo) -> Dict[str, Any]:
        """Capture the signals that drive a retention decision, for auditing.

        Args:
            movie_info: MovieInfo object containing movie details

        Returns:
            Dict[str, Any]: Snapshot of the rating, watch, and request signals.
        """
        requested_by = movie_info.requested_by
        is_admin_request = (
            not requested_by or requested_by.lower() in self.config.overseerr.admin_emails
        )

        return {
            "user_rating": movie_info.user_rating,
            "avg_external_rating": self._determine_average_external_rating(movie_info),
            "last_watched": movie_info.last_watched,
            "added_at": movie_info.added_at,
            "requested_by": requested_by,
            "is_admin_request": is_admin_request,
            "imdb_top_250": self._is_imdb_top_250(movie_info),
        }

    def _retention_window(
        self, movie_info: MovieInfo, inputs: Dict[str, Any]
    ) -> Tuple[RetentionReason, int]:
        """Determine the retention window for a non-protected movie.

        Once a user has rated a movie, their own rating decides retention; the
        external rating only ever protects (handled in _evaluate_retention) and
        never shortens the window. Unrated movies get a watch window based on
        whether an admin or a regular user requested them.

        Args:
            movie_info: MovieInfo object containing movie details
            inputs: Decision-input snapshot from _decision_inputs

        Returns:
            Tuple[RetentionReason, int]: The reason code and retention days.
        """
        rating_threshold = self.config.rating_threshold
        days_threshold = self.config.days_threshold

        if movie_info.user_rating:
            if movie_info.user_rating <= rating_threshold.low_rating:
                return RetentionReason.LOW_USER_RATING, days_threshold.low_rating
            return RetentionReason.MEH_USER_RATING, days_threshold.mid

        if inputs["is_admin_request"]:
            return RetentionReason.UNRATED_ADMIN, days_threshold.admin
        return RetentionReason.UNRATED_USER, days_threshold.user

    def _evaluate_retention(self, movie_info: MovieInfo) -> RetentionDecision:
        """Evaluate a movie against the retention policy.

        Protections (a high user rating, IMDB Top 250 membership, or a high
        average external rating) keep a movie forever. Otherwise the movie is
        assigned a retention window and an expiry date measured from its last
        activity.

        Args:
            movie_info: MovieInfo object containing movie details

        Returns:
            RetentionDecision: The reason, expiry date, retention days, and the
                inputs that drove the outcome.
        """
        inputs = self._decision_inputs(movie_info)
        rating_threshold = self.config.rating_threshold

        if movie_info.user_rating and movie_info.user_rating >= rating_threshold.admin:
            return RetentionDecision(RetentionReason.PROTECTED_USER_RATING, None, None, inputs)

        if inputs["imdb_top_250"]:
            return RetentionDecision(RetentionReason.PROTECTED_IMDB_TOP_250, None, None, inputs)

        avg_external = inputs["avg_external_rating"]
        if avg_external is not None and avg_external >= 8:
            return RetentionDecision(
                RetentionReason.PROTECTED_HIGH_EXTERNAL_RATING, None, None, inputs
            )

        reason, retention_days = self._retention_window(movie_info, inputs)
        last_activity = movie_info.last_watched or movie_info.added_at
        expires_at = last_activity + timedelta(days=retention_days)

        return RetentionDecision(reason, expires_at, retention_days, inputs)

    def _is_expired(self, expires_at: Optional[datetime]) -> bool:
        """
        Check if a movie has expired based on the expiry date.

        Args:
            expires_at: Datetime when the movie will expire

        Returns:
            True if the movie has expired, False otherwise
        """
        return expires_at and datetime.now() >= expires_at

    def _will_expire_soon(self, expires_at: Optional[datetime], days: int = 30) -> bool:
        """
        Check if a movie will expire within a specified number of days.

        Args:
            expires_at: Datetime when the movie will expire
            days: Number of days to check for expiry

        Returns:
            True if the movie will expire within the specified days, False otherwise
        """
        return expires_at and datetime.now() <= expires_at <= datetime.now() + timedelta(days=days)

    def _get_movie_info(self, radarr_movie: dict, tmdb_id: str) -> MovieInfo:
        """
        Create a MovieInfo object with data from Plex and Radarr.

        Args:
            radarr_movie: Movie information from Radarr
            tmdb_id: TMDB ID of the movie

        Returns:
            MovieInfo object containing combined movie information

        Raises:
            NotFound: If the movie cannot be found in Plex
        """
        # Get the Overseerr request for the movie if it exists
        overseerr_request = next(
            iter(filter(lambda x: x["media"]["tmdbId"] == int(tmdb_id), self.overseerr_requests)),
            {},
        )

        plex_movie = self.plex.library.section("Movies").getGuid(f"tmdb://{tmdb_id}")
        movie_info = MovieInfo(
            title=radarr_movie["title"],
            tmdb_id=tmdb_id,
            radarr_id=radarr_movie["id"],
            added_at=plex_movie.addedAt,
            external_ratings=self.get_external_ratings(radarr_movie),
            requested_by=overseerr_request.get("requestedBy", {}).get("email", None),
            last_watched=self._get_last_watched(plex_movie),
            user_rating=plex_movie.userRating,
        )

        # Evaluate retention and record the resulting decision on the movie
        movie_info.decision = self._evaluate_retention(movie_info)
        movie_info.expires_at = movie_info.decision.expires_at

        if self._will_expire_soon(movie_info.expires_at, self.config.audit.expiring_soon_days):
            self.upcoming_movies.append(movie_info)

            tqdm.write(
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]} - movie_cleaner - INFO - "
                f"{movie_info.title} will expire on "
                f"{movie_info.expires_at.strftime('%Y-%m-%d')}! "
                f"Last Watched: {movie_info.last_watched}, "
                f"Added: {movie_info.added_at}, "
                f"Rating: {movie_info.user_rating}, "
                f"Avg External Rating: {movie_info.decision.inputs['avg_external_rating']}"
            )

        return movie_info

    def _get_last_watched(self, plex_movie) -> datetime | None:
        """
        Get the last watched timestamp for any user from Tautulli.

        Args:
            plex_movie: Plex movie object

        Returns:
            datetime of last watch or None if never watched
        """
        return self.tautulli.get_last_watched(plex_movie.ratingKey)

    def _should_delete_movie(self, movie: MovieInfo) -> bool:
        """
        Determine if a movie should be deleted based on expiration date.

        Args:
            movie: MovieInfo object to evaluate

        Returns:
            True if movie should be deleted, False if it should be kept
        """
        return self._is_expired(movie.expires_at)

    def _record_expiring(self) -> None:
        """Write audit events for every movie that will expire soon."""
        for movie_info in self.upcoming_movies:
            self.audit.record_expiring(movie_info, movie_info.decision)

    def _delete_movies(self, movies: List[MovieInfo], dry_run: bool = False) -> int:
        """Delete movies from all configured Radarr instances and audit each deletion.

        For each movie this looks up its per-instance entries in combined_movies, logs the
        deletion attempt, deletes from each instance that has the movie (unless this is a dry
        run), and appends an audit event capturing the freed space, instances, and the reason
        the movie was scheduled for deletion.

        Args:
            movies: MovieInfo objects (each carrying its retention decision) to delete.
            dry_run: If True, only logs and audits what would be deleted. Defaults to False.

        Returns:
            int: Total bytes freed (or that would be freed, in a dry run).
        """
        total_freed = 0

        for movie_info in movies:
            entries = self.combined_movies[str(movie_info.tmdb_id)]
            action = "Would delete" if dry_run else "Attempting to delete"
            logger.info(f"{action} {movie_info.title}...")

            if dry_run:
                size = sum(entry.get("sizeOnDisk", 0) for entry in entries)
                instances = [entry["instance"].config.name for entry in entries]
                total_freed += size
                self.audit.record_deletion(
                    movie_info, movie_info.decision, instances, size, dry_run=True
                )
                continue

            freed = 0
            deleted_instances = []
            for entry in entries:
                if entry["instance"].delete_movie(entry["id"]):
                    freed += entry.get("sizeOnDisk", 0)
                    deleted_instances.append(entry["instance"].config.name)
                    logger.info("Done!")

            total_freed += freed
            self.audit.record_deletion(
                movie_info, movie_info.decision, deleted_instances, freed, dry_run=False
            )

        return total_freed

    def _log_statistics(self, deleted: List[MovieInfo], total: int) -> None:
        """
        Log summary statistics of the cleanup operation.

        Args:
            deleted: List of MovieInfo objects that were deleted
            total: Total number of movies processed
        """
        logger.info(f"Movies Deleted: {len(deleted)}")
        logger.info(f"Movies Kept: {total - len(deleted)}")
        logger.info(f"Movies Scheduled for Deletion Soon: {len(self.upcoming_movies)}")
