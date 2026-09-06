output "environment" {
  value = var.environment
}

output "media_bucket_name" {
  value = aws_s3_bucket.media.id
}

output "media_kms_key_arn" {
  value = aws_kms_key.media.arn
}

output "compute_instance_profile_name" {
  value = aws_iam_instance_profile.compute.name
}
