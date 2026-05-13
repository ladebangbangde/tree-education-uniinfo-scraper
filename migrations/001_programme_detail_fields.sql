ALTER TABLE programme
ADD COLUMN scholarships_available TINYINT NULL AFTER tuition_text_raw,
ADD COLUMN apply_date_text VARCHAR(128) NULL AFTER scholarships_available,
ADD COLUMN start_date_text VARCHAR(128) NULL AFTER apply_date_text,
ADD COLUMN teaching_language VARCHAR(128) NULL AFTER start_date_text,
ADD COLUMN detail_crawled_at DATETIME NULL AFTER teaching_language,
ADD COLUMN detail_source_hash VARCHAR(64) NULL AFTER detail_crawled_at;

CREATE TABLE programme_detail (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    programme_id BIGINT NOT NULL,
    overview TEXT NULL,
    description TEXT NULL,
    career_opportunities TEXT NULL,
    academic_requirements TEXT NULL,
    english_requirements TEXT NULL,
    other_requirements TEXT NULL,
    application_deadline_text VARCHAR(255) NULL,
    application_url VARCHAR(1024) NULL,
    official_programme_url VARCHAR(1024) NULL,
    source_url VARCHAR(1024) NULL,
    source_hash VARCHAR(64) NULL,
    last_crawled_at DATETIME NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_programme_detail_programme_id (programme_id),
    CONSTRAINT fk_programme_detail_programme
        FOREIGN KEY (programme_id) REFERENCES programme(id)
        ON DELETE CASCADE
);

CREATE TABLE programme_intake (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    programme_id BIGINT NOT NULL,
    intake_date_text VARCHAR(128) NULL,
    apply_date_text VARCHAR(128) NULL,
    start_date_text VARCHAR(128) NULL,
    intake_year INT NULL,
    intake_month INT NULL,
    source_url VARCHAR(1024) NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_programme_intake (
        programme_id,
        apply_date_text,
        start_date_text
    ),
    CONSTRAINT fk_programme_intake_programme
        FOREIGN KEY (programme_id) REFERENCES programme(id)
        ON DELETE CASCADE
);

CREATE TABLE programme_language_requirement (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    programme_id BIGINT NOT NULL,
    teaching_language VARCHAR(128) NULL,
    ielts_overall DECIMAL(3,1) NULL,
    ielts_listening DECIMAL(3,1) NULL,
    ielts_reading DECIMAL(3,1) NULL,
    ielts_writing DECIMAL(3,1) NULL,
    ielts_speaking DECIMAL(3,1) NULL,
    toefl_overall INT NULL,
    pte_overall INT NULL,
    raw_text TEXT NULL,
    source_url VARCHAR(1024) NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    UNIQUE KEY uk_programme_language_programme_id (programme_id),
    CONSTRAINT fk_programme_language_programme
        FOREIGN KEY (programme_id) REFERENCES programme(id)
        ON DELETE CASCADE
);

CREATE TABLE programme_application_requirement (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    programme_id BIGINT NOT NULL,
    requirement_type VARCHAR(128) NULL,
    title VARCHAR(255) NULL,
    raw_text TEXT NULL,
    normalized_text TEXT NULL,
    source_url VARCHAR(1024) NULL,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    KEY idx_programme_requirement_programme_id (programme_id),
    CONSTRAINT fk_programme_requirement_programme
        FOREIGN KEY (programme_id) REFERENCES programme(id)
        ON DELETE CASCADE
);
