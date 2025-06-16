import boto3
import os
from dotenv import load_dotenv

# Cargar variables desde .env
load_dotenv()

# Crear cliente S3
s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION")
)

# Nombre del bucket
BUCKET_NAME = os.getenv("BUCKET_NAME")