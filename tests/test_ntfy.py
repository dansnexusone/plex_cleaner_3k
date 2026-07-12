from datetime import datetime, timedelta
from unittest.mock import patch

from models.config import NtfyConfig
from models.movie_info import MovieInfo
from services.ntfy import NtfyNotifier


def _movie(title: str, days_until_expiry: int) -> MovieInfo:
    return MovieInfo(
        title=title,
        tmdb_id=1,
        radarr_id=1,
        added_at=datetime.now(),
        external_ratings=None,
        requested_by=None,
        last_watched=None,
        user_rating=None,
        expires_at=datetime.now() + timedelta(days=days_until_expiry),
    )


@patch("services.ntfy.requests.post")
def test_disabled_sends_nothing(post):
    NtfyNotifier(NtfyConfig(enabled=False, topic="movies")).notify(
        [_movie("A", 0)], [], dry_run=False
    )
    post.assert_not_called()


@patch("services.ntfy.requests.post")
def test_missing_topic_sends_nothing(post):
    NtfyNotifier(NtfyConfig(enabled=True, topic="")).notify(
        [_movie("A", 0)], [], dry_run=False
    )
    post.assert_not_called()


@patch("services.ntfy.requests.post")
def test_quiet_run_sends_nothing(post):
    NtfyNotifier(NtfyConfig(enabled=True, topic="movies")).notify([], [], dry_run=False)
    post.assert_not_called()


@patch("services.ntfy.requests.post")
def test_reports_deletions_and_imminent(post):
    NtfyNotifier(
        NtfyConfig(enabled=True, topic="movies", server="https://ntfy.sh")
    ).notify([_movie("Gone", 0)], [_movie("Soon", 1)], dry_run=False)

    post.assert_called_once()
    assert post.call_args.args[0] == "https://ntfy.sh/movies"
    body = post.call_args.kwargs["data"]
    assert b"Gone" in body and b"Soon" in body
