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
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_failed_task_active (task_type, source_id, source_url, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
