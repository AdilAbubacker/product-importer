import boto3
from botocore.client import Config
from django.conf import settings


def get_r2_client():
    """
    Returns a boto3 S3 client configured for Cloudflare R2.
    """
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name=settings.R2_REGION,
        config=Config(signature_version="s3v4"),
    )


def generate_presigned_put_url(object_key: str, content_type: str = "application/octet-stream", expires_in: int = 600) -> str:
    """
    Generate a presigned PUT URL for uploading a single object.
    """
    s3 = get_r2_client()
    return s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.R2_BUCKET_NAME,
            "Key": object_key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,  # seconds
    )


def generate_presigned_get_url(object_key: str, expires_in: int = 600) -> str:
    s3 = get_r2_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.R2_BUCKET_NAME,
            "Key": object_key,
        },
        ExpiresIn=expires_in,
    )