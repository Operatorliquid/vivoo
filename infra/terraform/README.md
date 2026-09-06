# CourtVision AWS foundation

This stack creates the private, versioned and KMS-encrypted S3 media bucket plus
the least-privilege EC2 instance profile used by the API and media worker. The
bucket blocks every public access path, rejects non-TLS requests, archives older
media and removes incomplete uploads.

```bash
terraform init
terraform plan -var='environment=pilot'
terraform apply -var='environment=pilot'
```

After applying, attach `compute_instance_profile_name` to the CourtVision EC2
instance and set `AWS_S3_MEDIA_BUCKET` and `AWS_REGION` in the deployment env.
Do not copy long-lived AWS access keys into `.env`; the SDK must use the instance
role. Production applies require a reviewed remote Terraform state backend.
