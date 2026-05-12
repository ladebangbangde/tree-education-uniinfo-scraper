# Crawler Policy

This project is designed for internal testing and data-model validation using only public, unauthenticated pages.

## Mandatory rules

- Crawl only visible public pages.
- Do not log in, create accounts, or access profile, wishlist, personalization, or private data.
- Do not bypass CAPTCHA, paywalls, rate limits, bot challenges, or robots.txt.
- Check `robots.txt` before every page fetch. Disallowed URLs are skipped and logged as warnings.
- Use single-threaded crawling by default.
- Sleep a random 1-3 seconds between requests unless environment variables configure a wider delay.
- Store `source_url`, `last_crawled_at`, and `source_hash` with crawled records.
- Save HTML snapshots only for traceable test evidence and parser debugging.
- Do not use long text snapshots directly for commercial display.

## Operational guidance

Start with very small limits such as `--limit 10`. If the target site changes markup or returns a bot challenge, stop crawling and update the parser or policy instead of attempting to bypass protections.
