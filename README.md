# tree-education-uniinfo-scraper

A Python 3.11+ crawler for collecting public, unauthenticated university and bachelor-programme information for internal testing and data-model validation. The first-stage source is Bachelorsportal public pages.

> This project is not intended for commercial republication of scraped long-form content.

## Compliance scope

The crawler is intentionally conservative:

1. It reads only publicly visible pages.
2. It does not log in.
3. It does not bypass CAPTCHA, anti-bot pages, paywalls, or access controls.
4. It checks `robots.txt` before requests and skips disallowed URLs.
5. It is single-threaded by default.
6. It sleeps a random 1-3 seconds between requests by default.
7. It stores `source_url`, `last_crawled_at`, and `source_hash` for traceability.
8. HTML snapshots are saved as internal test evidence under `data/snapshots/`.
9. Long text fields/snapshots should not be directly displayed commercially.
10. Every persisted field must be traceable to the source URL.

See `docs/crawler-policy.md` for the detailed policy.

## Project structure

```text
tree-education-uniinfo-scraper/
├── README.md
├── requirements.txt
├── .env.example
├── docker-compose.yml
├── docs/
├── sql/
└── src/
```

Key modules:

- `src/main.py` — Typer CLI.
- `src/crawler/browser.py` — Playwright wrapper with retries, timeouts, image blocking, and delays.
- `src/crawler/robots.py` — robots.txt compliance check.
- `src/crawler/html_snapshot.py` — SHA-256 HTML snapshots.
- `src/sources/bachelorsportal/` — Bachelorsportal URL builders and parsers.
- `src/pipelines/normalize.py` — duration, tuition, rating, and count normalization.
- `src/pipelines/persist.py` — SQLAlchemy upsert helpers.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

## MySQL startup

```bash
docker compose up -d mysql
```

Optional services are included:

```bash
docker compose up -d redis adminer
```

Adminer runs on <http://localhost:8080>.

Default MySQL settings:

- Database: `tree_education_uniinfo`
- User: `tree_user`
- Password: `tree_password`
- Root password: `root_password`

## Environment variables

`.env.example` contains:

```dotenv
DATABASE_URL=mysql+pymysql://tree_user:tree_password@localhost:3306/tree_education_uniinfo
HEADLESS=true
REQUEST_MIN_DELAY=1
REQUEST_MAX_DELAY=3
CRAWLER_USER_AGENT=Mozilla/5.0 TreeEducationBot/0.1
SNAPSHOT_DIR=data/snapshots
BLOCK_IMAGES=true
REQUEST_TIMEOUT_MS=30000
```

Set `HEADLESS=false` if you need to watch a local debugging browser session.

## Database initialization

The Docker MySQL container loads `sql/init.sql` and `sql/indexes.sql` on first startup. You can also create tables with SQLAlchemy:

```bash
python -m src.main init-db
```

## CLI usage

### Crawl university list

```bash
python -m src.main crawl-universities --country united-kingdom --limit 10
```

This opens `https://www.bachelorsportal.com/search/universities/bachelor/united-kingdom`, extracts the first 10 university cards where possible, saves an HTML snapshot, and upserts rows into `university`.

### Crawl university detail

```bash
python -m src.main crawl-university-detail --university-id 1
```

This reads `university.source_url`, fetches the public detail page, saves a snapshot, updates `university`, and attempts to write related public data into:

- `university_statistics`
- `university_content_section`
- `university_ranking`
- `scholarship`
- `campus_location`
- `university_review_summary`

### Crawl programmes

```bash
python -m src.main crawl-programmes --university-id 1 --limit 20
```

This fetches the public programmes page inferred from the stored university source URL and upserts programme list entries into `programme`.

## Database tables

- `university`: basic university profile and traceability columns.
- `university_statistics`: ranking/staff/student/count fields.
- `university_content_section`: overview/history/education/research/career/housing/library/campus life/accreditation text sections.
- `programme`: bachelor programme data with normalized duration and tuition fields.
- `university_ranking`: ranking system/value/year/source data.
- `scholarship`: public scholarship snippets.
- `campus_location`: public campus/location data.
- `university_review_summary`: aggregate review summary only.

See `docs/data-schema.md` for deduplication rules.

## Parser robustness

Bachelorsportal markup can change. Parsers therefore:

1. Prefer semantic attributes and text.
2. Fall back to common CSS/card selectors.
3. Use regex extraction as a final fallback.
4. Allow every extracted field to be `None`.

If the website returns a CAPTCHA or blocks access, stop and do not attempt to bypass it.

## Common issues

### `playwright` browser is missing

Run:

```bash
playwright install chromium
```

### MySQL connection fails

Check Docker health and credentials:

```bash
docker compose ps
```

Confirm `.env` has the same `DATABASE_URL` as `.env.example`.

### No rows are extracted

Possible causes:

- `robots.txt` disallowed the URL.
- The public page layout changed.
- The site returned an interstitial, CAPTCHA, or blocked response.
- The country query parameter format changed.

Do not bypass protections. Inspect the saved snapshot if one exists, then update selectors responsibly.

## P0 验收步骤

> 验收前请确认 `.env` 中 `DATABASE_URL` 指向可用的 MySQL 8 实例，并已执行 `playwright install chromium`。爬虫保持单线程、低频请求，并在每次请求前检查 `robots.txt`。

1. 启动 MySQL：

```bash
docker compose up -d mysql
```

2. 初始化数据库表：

```bash
python -m src.main init-db
```

3. 抓取英国本科大学列表页前 10 条公开结果：

```bash
python -m src.main crawl-universities --country united-kingdom --limit 10
```

4. 如果命令没有报错但写入 0 条，请先查看最近保存的 HTML snapshot，不要绕过验证码、不要绕过 robots、不要加代理池：

```bash
find data/snapshots/bachelorsportal -type f | sort | tail -5
```

5. 使用 SQL 检查 `university` 表是否至少写入 1 条有效学校数据，且 `name`、`source_url`、`source_university_id` 非空：

```sql
SELECT COUNT(*) AS university_count
FROM university;

SELECT id,
       name,
       source_url,
       source_university_id,
       country,
       city,
       location_text,
       bachelor_count,
       scholarship_count,
       rating,
       review_count,
       source_hash,
       last_crawled_at
FROM university
ORDER BY id DESC
LIMIT 10;

SELECT COUNT(*) AS invalid_identity_count
FROM university
WHERE name IS NULL OR name = ''
   OR source_url IS NULL OR source_url = ''
   OR source_university_id IS NULL OR source_university_id = '';
```

6. 运行基础测试：

```bash
python -m unittest discover -s tests -v
```
