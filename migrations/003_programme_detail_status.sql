ALTER TABLE programme
ADD COLUMN detail_status VARCHAR(32) DEFAULT 'pending' AFTER teaching_language,
ADD COLUMN detail_missing_fields VARCHAR(512) NULL AFTER detail_status,
ADD COLUMN detail_error_message TEXT NULL AFTER detail_missing_fields;

UPDATE programme SET detail_status = 'pending' WHERE detail_status IS NULL;
