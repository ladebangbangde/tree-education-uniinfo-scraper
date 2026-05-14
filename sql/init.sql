CREATE DATABASE IF NOT EXISTS tree_education_uniinfo CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE tree_education_uniinfo;

CREATE TABLE IF NOT EXISTS university (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  source_site VARCHAR(64),
  source_university_id VARCHAR(128),
  source_url VARCHAR(1024),
  name VARCHAR(255),
  country VARCHAR(128),
  city VARCHAR(128),
  location_text VARCHAR(255),
  institution_type VARCHAR(128),
  bachelor_count INT,
  scholarship_count INT,
  ranking_text VARCHAR(255),
  rating DECIMAL(3,2),
  review_count INT,
  description TEXT,
  official_website_url VARCHAR(1024),
  is_featured TINYINT,
  last_crawled_at DATETIME,
  source_hash VARCHAR(64),
  created_at DATETIME,
  updated_at DATETIME,
  UNIQUE KEY uq_university_source (source_site, source_university_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS university_statistics (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  university_id BIGINT,
  ranking VARCHAR(255),
  academic_staff_count INT,
  total_students INT,
  international_students INT,
  female_students INT,
  institution_type VARCHAR(128),
  bachelor_count INT,
  scholarship_count INT,
  created_at DATETIME,
  updated_at DATETIME,
  UNIQUE KEY uq_statistics_university (university_id),
  CONSTRAINT fk_statistics_university FOREIGN KEY (university_id) REFERENCES university(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS university_content_section (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  university_id BIGINT,
  section_type VARCHAR(128),
  title VARCHAR(255),
  content_summary TEXT,
  source_content TEXT,
  source_url VARCHAR(1024),
  created_at DATETIME,
  updated_at DATETIME,
  UNIQUE KEY uq_content_section (university_id, section_type),
  CONSTRAINT fk_content_university FOREIGN KEY (university_id) REFERENCES university(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS programme (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  university_id BIGINT,
  source_programme_id VARCHAR(128),
  source_url VARCHAR(1024),
  name VARCHAR(500),
  degree_type VARCHAR(128),
  discipline VARCHAR(255),
  attendance_mode VARCHAR(128),
  delivery_mode VARCHAR(128),
  duration_value INT,
  duration_unit VARCHAR(64),
  tuition_amount DECIMAL(12,2),
  tuition_currency VARCHAR(16),
  tuition_period VARCHAR(64),
  city VARCHAR(128),
  country VARCHAR(128),
  is_featured TINYINT,
  tuition_text_raw VARCHAR(255),
  scholarships_available TINYINT NULL,
  apply_date_text VARCHAR(128) NULL,
  start_date_text VARCHAR(128) NULL,
  teaching_language VARCHAR(128) NULL,
  detail_crawled_at DATETIME NULL,
  detail_source_hash VARCHAR(64) NULL,
  duration_text_raw VARCHAR(255),
  last_crawled_at DATETIME,
  source_hash VARCHAR(64),
  created_at DATETIME,
  updated_at DATETIME,
  UNIQUE KEY uq_programme_source (university_id, source_programme_id),
  CONSTRAINT fk_programme_university FOREIGN KEY (university_id) REFERENCES university(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE IF NOT EXISTS programme_detail (
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
  CONSTRAINT fk_programme_detail_programme FOREIGN KEY (programme_id) REFERENCES programme(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS programme_intake (
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
  UNIQUE KEY uk_programme_intake (programme_id, apply_date_text, start_date_text),
  CONSTRAINT fk_programme_intake_programme FOREIGN KEY (programme_id) REFERENCES programme(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS programme_language_requirement (
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
  CONSTRAINT fk_programme_language_programme FOREIGN KEY (programme_id) REFERENCES programme(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS programme_application_requirement (
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
  CONSTRAINT fk_programme_requirement_programme FOREIGN KEY (programme_id) REFERENCES programme(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS university_ranking (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  university_id BIGINT,
  ranking_system VARCHAR(128),
  ranking_value VARCHAR(128),
  region_scope VARCHAR(128),
  year INT,
  trend_text VARCHAR(255),
  source_name VARCHAR(255),
  source_url VARCHAR(1024),
  created_at DATETIME,
  updated_at DATETIME,
  UNIQUE KEY uq_ranking (university_id, ranking_system, year),
  CONSTRAINT fk_ranking_university FOREIGN KEY (university_id) REFERENCES university(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS scholarship (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  university_id BIGINT NULL,
  name VARCHAR(255),
  provider_type VARCHAR(128),
  provider_name VARCHAR(255),
  scholarship_type VARCHAR(128),
  amount_text VARCHAR(255),
  amount_value DECIMAL(12,2),
  currency VARCHAR(16),
  deadline_text VARCHAR(255),
  deadline_date DATE,
  location_text VARCHAR(255),
  source_url VARCHAR(1024),
  created_at DATETIME,
  updated_at DATETIME,
  UNIQUE KEY uq_scholarship (university_id, name, deadline_text),
  CONSTRAINT fk_scholarship_university FOREIGN KEY (university_id) REFERENCES university(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS campus_location (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  university_id BIGINT,
  campus_name VARCHAR(255),
  country VARCHAR(128),
  city VARCHAR(128),
  map_url VARCHAR(1024),
  address_text VARCHAR(512),
  created_at DATETIME,
  updated_at DATETIME,
  UNIQUE KEY uq_campus (university_id, campus_name, city),
  CONSTRAINT fk_campus_university FOREIGN KEY (university_id) REFERENCES university(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS university_review_summary (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  university_id BIGINT,
  overall_rating DECIMAL(3,2),
  review_count INT,
  five_star_count INT,
  four_star_count INT,
  three_star_count INT,
  two_star_count INT,
  one_star_count INT,
  student_teacher_interaction DECIMAL(3,2),
  student_diversity DECIMAL(3,2),
  admission_process DECIMAL(3,2),
  quality_of_student_life DECIMAL(3,2),
  career_development DECIMAL(3,2),
  created_at DATETIME,
  updated_at DATETIME,
  UNIQUE KEY uq_review_summary_university (university_id),
  CONSTRAINT fk_review_university FOREIGN KEY (university_id) REFERENCES university(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS crawl_failed_task (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_type VARCHAR(64) NOT NULL,
  source_id BIGINT NULL,
  source_name VARCHAR(255) NULL,
  source_url VARCHAR(1024) NULL,
  error_type VARCHAR(128) NULL,
  error_message TEXT NULL,
  retry_count INT DEFAULT 0,
  status VARCHAR(32) DEFAULT 'failed',
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  KEY idx_crawl_failed_task_retry (status, retry_count, updated_at),
  KEY idx_crawl_failed_task_dedupe (task_type, source_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
