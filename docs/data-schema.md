# Data Schema

The schema is initialized by `sql/init.sql` and optimized by `sql/indexes.sql`.

## Tables

- `university`: source-traceable university profile data, including `source_url`, `source_hash`, and `last_crawled_at`.
- `university_statistics`: key statistics such as students, staff, rankings, and counts.
- `university_content_section`: public overview-style text sections. Long source text is retained as test snapshot data only.
- `programme`: bachelor programme list items with normalized duration and tuition fields.
- `university_ranking`: rankings by system/year.
- `scholarship`: scholarship snippets and amount/deadline fields when publicly visible.
- `campus_location`: public campus/location summaries.
- `university_review_summary`: aggregate review/rating metrics only, with no private user-level review data.

## Deduplication keys

- `university`: `source_site + source_university_id`
- `programme`: `university_id + source_programme_id`
- `university_ranking`: `university_id + ranking_system + year`
- `scholarship`: `university_id + name + deadline_text`
- `campus_location`: `university_id + campus_name + city`
