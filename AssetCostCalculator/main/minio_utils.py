from django.conf import settings
from minio import Minio
from minio.error import S3Error

def get_minio_client():
    """
    Создает и возвращает клиент MinIO
    """
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_USE_SSL
    )

