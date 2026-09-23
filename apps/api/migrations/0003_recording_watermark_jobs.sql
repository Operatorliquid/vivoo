ALTER TABLE processing_jobs
DROP CONSTRAINT IF EXISTS processing_jobs_job_type_check;

ALTER TABLE processing_jobs
ADD CONSTRAINT processing_jobs_job_type_check
CHECK (job_type IN (
  'assemble_highlight',
  'watermark_recording',
  'transcode',
  'thumbnail',
  'send_delivery',
  'expire_media'
));
