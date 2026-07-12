

## Overview

plex_cleaner_3k is an automated solution for managing your Plex movie library by intelligently cleaning up movies based on watch history, ratings, and custom retention rules. It integrates with Radarr, Overseerr, and Tautulli to make informed decisions about which content to keep or remove.

## Features

- Automated cleanup of movies from both 4K/UHD and 1080p libraries
- Smart retention rules based on:
  - Plex user ratings
  - External ratings (IMDB, Rotten Tomatoes, TMDB, Metacritic, Trakt)
  - Watch history
  - Request source (admin vs regular users)
  - High IMDB rating (configurable threshold)
- Service integrations:
  - Plex Media Server
  - Dual Radarr instances (4K and 1080p)
  - Overseerr
  - Tautulli
- Dry-run mode for testing deletions
- JSONL audit log recording every deletion (and upcoming expiry) with the reason and the data behind the decision
- Human-readable expiring-soon digest, ideal for surfacing via MOTD on SSH login
- Optional ntfy push notifications when movies are deleted or about to be
- Detailed logging

## Requirements

- Python 3.12+
- Plex Media Server
- Radarr (4K and 1080p instances)
- Overseerr
- Tautulli
- Docker (optional)

## Installation

### Option 1: Using Docker

1. Clone the repository:

```bash
git clone https://github.com/yourusername/plex_cleaner_3k.git
cd plex_cleaner_3k
```

2. Create configuration files (see Configuration section)

3. Build and run with Docker:

```bash
docker build -t plex-cleaner .
docker run \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -v /var/lib/plex-cleaner:/app/output \
  --env-file .env plex-cleaner
```

The second mount persists the audit log and expiring-soon summary to the host (see [Audit Log & Notifications](#audit-log--notifications)).

### Option 2: Manual Installation

1. Clone the repository
2. Set up virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

The application uses two configuration files:

1. `config.yaml` for general settings
2. `.env` for sensitive information (API keys, passwords)

### Environment Variables (.env)

Create a `.env` file in the project root:

```bash
PLEX_TOKEN=your-plex-token
TAUTULLI_API_KEY=your-tautulli-api-key
RADARR_4K_API_KEY=your-radarr-4k-api-key
RADARR_1080P_API_KEY=your-radarr-hd-api-key
OVERSEERR_API_KEY=your-overseerr-api-key
OVERSEERR_PASSWORD=your-overseerr-password

# TAUTULLI 
TAUTULLI_URL=your-tautulli-url
TAUTULLI_API_KEY=your-tautulli-api-key

# PLEX
PLEX_URL=your-plex-url
PLEX_TOKEN=your-plex-token

# RADARR
RADARR_INSTANCES=4k,1080p # Optional if you have more than one Radarr instance
RADARR_4K_URL=your-radarr-4k-url
RADARR_4K_API_KEY=your-radarr-4k-api-key
RADARR_1080P_URL=your-radarr-1080p-url
RADARR_1080P_API_KEY=your-radarr-1080p-api-key

# OVERSEERR
OVERSEERR_URL=your-overseerr-url
OVERSEERR_API_KEY=your-overseerr-api-key
OVERSEERR_EMAIL=your-overseerr-admin-email
OVERSEERR_PASSWORD=your-overseerr-admin-password
OVERSEERR_ADMIN_EMAILS=your-admin-email-address-1,your-admin-email-address-2,...

# NTFY (optional — overrides the ntfy block in config.yaml)
NTFY_ENABLED=true
NTFY_TOPIC=your-ntfy-topic
NTFY_SERVER=https://ntfy.sh
```

### Configuration File (config.yaml)

Create a `config.yaml` file:

```yaml
deletion_threshold:
  days:
    users:
      admin: 365  # Retain admin-requested movies for a year
      user: 14    # Retain user-requested movies for two weeks
    rules:
      low_rated: 30  # Movies rated <= 1.5 stars: remove after 30 days
      mid: 90        # "Meh" movies rated between 1.5 and 2.5 stars: remove after 90 days
  rating:
    users:
      admin: 5  # Movies rated >= 2.5 stars are protected from deletion
      user: 5
    rules:
      low: 3    # Movies rated <= 1.5 stars use the low_rated window
      imdb_protect: 8.0  # Movies with an IMDB rating >= this are protected from deletion

audit:
  log_path: output/deletions.jsonl        # Append-only JSONL trail of deletions and expiring-soon events
  summary_path: output/expiring_soon.txt  # Human-readable digest (e.g. for MOTD)
  expiring_soon_days: 60                   # Window for the digest and "expiring soon" audit events

ntfy:
  enabled: false           # Set true to push notifications (see below)
  server: https://ntfy.sh  # ntfy server; override with NTFY_SERVER
  topic: ""                # Your ntfy topic; override with NTFY_TOPIC
  priority: default        # min, low, default, high, urgent
  notify_within_days: 1    # Also notify when a movie is within this many days of deletion
```

## Usage

### Basic Usage

Run the cleaner:

```bash
python main.py
```

### Dry Run Mode

Test without deleting:

```bash
python main.py --dry-run
```

### Docker Usage

```bash
# Normal run
docker run \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -v /var/lib/plex-cleaner:/app/output \
  --env-file .env plex-cleaner

# Dry run
docker run \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -v /var/lib/plex-cleaner:/app/output \
  --env-file .env plex-cleaner --dry-run
```

## How It Works

The cleaner evaluates movies based on:

1. Watch history from Tautulli
2. User ratings from Plex
3. External ratings (IMDB, Rotten Tomatoes, etc.)
4. Request source from Overseerr
5. Age of content

### Retention Rules

A movie is **protected (never deleted)** if any of these hold:

- Your Plex rating is ≥ 2.5 stars
- Its IMDB rating is ≥ 8.0 (configurable via `imdb_protect`)
- Its average external rating is ≥ 8/10

Otherwise it is assigned a retention window, measured from the last watch (or the date it was added, if never watched):

| Situation | Window (default) |
|-----------|------------------|
| Rated ≤ 1.5 stars | `low_rated` — 30 days |
| Rated between 1.5 and 2.5 stars | `mid` — 90 days |
| Unrated, admin-requested (or no request record) | `admin` — 365 days |
| Unrated, user-requested | `user` — 14 days |

Once you've rated a movie, your own rating decides its window — external ratings only ever *protect* a movie, never shorten its retention.

## Audit Log & Notifications

Every run records what it did and why:

- **`output/deletions.jsonl`** — an append-only JSON-Lines audit trail. One object per event, with the action (`deleted`, `would_delete` in dry-run, or `expiring_soon`), the movie, the Radarr instances affected, bytes freed, the retention reason, and the inputs that drove the decision. Easy to grep or feed into other tools.
- **`output/expiring_soon.txt`** — a human-readable digest of movies expiring within `expiring_soon_days`, regenerated each run.

Example audit entry:

```json
{"ts": "2026-05-20T14:03:11", "run_id": "2026-05-20T14:00:00", "action": "deleted", "dry_run": false, "instances": ["radarr_4k"], "size_freed_bytes": 8400000000, "title": "Some Movie", "tmdb_id": 12345, "expires_at": "2026-05-06", "reason": "unrated_user", "retention_days": 14, "inputs": {"user_rating": null, "avg_external_rating": 6.2, "last_watched": null, "added_at": "2025-01-02T00:00:00", "requested_by": "x@y.com", "is_admin_request": false, "imdb_top_250": false}}
```

### Push notifications via ntfy

Enable the `ntfy` block in `config.yaml`, or set `NTFY_ENABLED=true` and `NTFY_TOPIC` in your `.env`, to get a push whenever a run does something worth knowing about:

- Movies were deleted this run, or
- A movie is within `notify_within_days` (default 1) of deletion — a last-chance heads-up before the next run removes it.

Runs where nothing was deleted and nothing is imminent send nothing. Disabled by default; a missing topic is treated as disabled.

### Surfacing the summary via MOTD

To see the expiring-soon digest each time you SSH into the host (no email plumbing required):

1. Bind-mount the container's output directory to a host path, e.g. `-v /var/lib/plex-cleaner:/app/output` (see [Docker Usage](#docker-usage)).
2. Install an `update-motd.d` hook on the host that prints the summary on login:

```bash
sudo tee /etc/update-motd.d/99-plex-cleaner > /dev/null <<'EOF'
#!/bin/sh
SUMMARY="/var/lib/plex-cleaner/expiring_soon.txt"
[ -f "$SUMMARY" ] || exit 0
printf '\n'; cat "$SUMMARY"; printf '\n'
EOF
sudo chmod +x /etc/update-motd.d/99-plex-cleaner
```

Adjust `SUMMARY` if you mounted the output elsewhere.

## Project Structure

```
plex_cleaner_3k/
├── models/
│   ├── config.py             # Configuration dataclasses
│   ├── external_rating.py    # External rating data structure
│   ├── movie_info.py         # Movie metadata + retention decision
│   └── retention_decision.py # Retention reason codes + decision result
├── services/
│   ├── audit.py              # JSONL deletion/expiry audit log
│   ├── config.py             # Config management
│   ├── overseerr.py          # Overseerr integration
│   ├── radarr.py             # Radarr API client
│   ├── summary.py            # Human-readable expiring-soon digest
│   └── tautulli.py           # Tautulli integration
├── output/                   # Audit log + summary (gitignored; mount in Docker)
├── .env                      # Environment variables (secrets)
├── config.yaml               # YAML configuration file
├── main.py                   # CLI entry point
├── movie_cleaner.py          # Core cleaning logic
├── requirements.txt          # Python dependencies
└── Dockerfile                # Container definition
```

## Security Notes

- Never commit your `.env` file to version control
- The `.env` file is included in `.gitignore` by default
- When using Docker, pass environment variables using the `--env-file` flag
- For production deployments, consider using a secrets management solution

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - See LICENSE file for details
