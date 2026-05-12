# Architecture

## Components

- `src/main.py`: Typer CLI entry point.
- `src/config.py`: environment-driven settings.
- `src/db.py`: SQLAlchemy engine, declarative base, and session scope.
- `src/models/`: ORM models for the MySQL tables.
- `src/crawler/`: browser, robots.txt, rate limiting, and HTML snapshots.
- `src/sources/bachelorsportal/`: site-specific URL builders and parsers.
- `src/pipelines/`: normalization, deduplication keys, and persistence/upsert helpers.
- `src/tasks/`: command orchestration for list, detail, and programme crawls.

## Flow

1. CLI command receives crawl parameters.
2. Task builds a public Bachelorsportal URL.
3. `robots.py` checks permission for the URL.
4. `rate_limit.py` sleeps 1-3 seconds.
5. `browser.py` fetches the page with Playwright using retries and a 30-second timeout.
6. `html_snapshot.py` saves the HTML and returns a SHA-256 hash.
7. Parsers extract best-effort partial data with nullable fields.
8. `persist.py` upserts rows using configured deduplication keys.

## Parser strategy

Parsers prefer semantic attributes and text, then common CSS/card patterns, then regex fallback. Missing fields return `None` so one absent element does not fail an entire crawl.
