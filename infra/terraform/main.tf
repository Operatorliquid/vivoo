terraform {
  required_version = ">= 1.8.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Application = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  resource_prefix = "${var.project_name}-${var.environment}"
  media_bucket    = "${local.resource_prefix}-media-${data.aws_caller_identity.current.account_id}"
}

data "aws_iam_policy_document" "media_kms" {
  # KMS key policies require Resource="*" to mean the key carrying this policy;
  # the principal is restricted to this AWS account's root identity.
  #checkov:skip=CKV_AWS_109:This is the account-root administration statement required by the KMS key policy.
  #checkov:skip=CKV_AWS_111:Resource star means only this KMS key in a key policy, not every AWS resource.
  #checkov:skip=CKV_AWS_356:AWS KMS key-policy statements require Resource star to identify the attached key.
  statement {
    sid       = "EnableAccountAdministration"
    effect    = "Allow"
    actions   = ["kms:*"]
    resources = ["*"]

    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
  }
}

resource "aws_kms_key" "media" {
  description             = "CourtVision private media encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  policy                  = data.aws_iam_policy_document.media_kms.json
}

resource "aws_kms_alias" "media" {
  name          = "alias/${local.resource_prefix}-media"
  target_key_id = aws_kms_key.media.key_id
}

# Application activity records provide the player-level media audit trail; raw
# S3 access logs would duplicate it without identifying the business actor.
# Processing is coordinated through authenticated API jobs, not S3 events.
# The pilot is intentionally single-region; versioning and KMS protect the media
# until cross-region disaster recovery is enabled for the production tier.
resource "aws_s3_bucket" "media" {
  #checkov:skip=CKV_AWS_18:Player-level access is audited by the application and direct public access is blocked.
  #checkov:skip=CKV2_AWS_62:Media processing uses the durable application job queue rather than bucket notifications.
  #checkov:skip=CKV_AWS_144:Cross-region replication is deferred to the production disaster-recovery tier.
  bucket = local.media_bucket
}

resource "aws_s3_bucket_ownership_controls" "media" {
  bucket = aws_s3_bucket.media.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "media" {
  bucket = aws_s3_bucket.media.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "media" {
  bucket = aws_s3_bucket.media.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "media" {
  bucket = aws_s3_bucket.media.id

  rule {
    bucket_key_enabled = true

    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.media.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "media" {
  bucket = aws_s3_bucket.media.id

  depends_on = [aws_s3_bucket_versioning.media]

  rule {
    id     = "media-retention"
    status = "Enabled"

    filter {}

    transition {
      days          = var.media_infrequent_access_after_days
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = var.media_archive_after_days
      storage_class = "GLACIER_IR"
    }

    expiration {
      days = var.media_max_retention_days
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

data "aws_iam_policy_document" "media_bucket" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.media.arn,
      "${aws_s3_bucket.media.arn}/*",
    ]

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "media" {
  bucket = aws_s3_bucket.media.id
  policy = data.aws_iam_policy_document.media_bucket.json
}

data "aws_iam_policy_document" "compute_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "compute" {
  name               = "${local.resource_prefix}-compute"
  assume_role_policy = data.aws_iam_policy_document.compute_assume_role.json
}

data "aws_iam_policy_document" "compute_media" {
  statement {
    sid = "MediaObjects"
    actions = [
      "s3:DeleteObject",
      "s3:DeleteObjectVersion",
      "s3:GetObject",
      "s3:ListBucket",
      "s3:PutObject",
    ]
    resources = [
      aws_s3_bucket.media.arn,
      "${aws_s3_bucket.media.arn}/*",
    ]
  }

  statement {
    sid = "MediaKms"
    actions = [
      "kms:Decrypt",
      "kms:Encrypt",
      "kms:GenerateDataKey",
    ]
    resources = [aws_kms_key.media.arn]
  }
}

resource "aws_iam_role_policy" "compute_media" {
  name   = "media-access"
  role   = aws_iam_role.compute.id
  policy = data.aws_iam_policy_document.compute_media.json
}

resource "aws_iam_instance_profile" "compute" {
  name = "${local.resource_prefix}-compute"
  role = aws_iam_role.compute.name
}
