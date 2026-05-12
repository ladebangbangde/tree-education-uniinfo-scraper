USE tree_education_uniinfo;
CREATE INDEX idx_university_country_city ON university(country, city);
CREATE INDEX idx_university_last_crawled ON university(last_crawled_at);
CREATE INDEX idx_programme_university ON programme(university_id);
CREATE INDEX idx_programme_country_city ON programme(country, city);
CREATE INDEX idx_ranking_university ON university_ranking(university_id);
CREATE INDEX idx_scholarship_university ON scholarship(university_id);
CREATE INDEX idx_campus_university ON campus_location(university_id);
