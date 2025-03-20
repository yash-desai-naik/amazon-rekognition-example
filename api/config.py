import os


from dotenv import load_dotenv

load_dotenv(override=True)

# AWS Configuration
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")

# S3 Configuration
BUCKET_NAME = os.environ.get("S3_BUCKET", "famouspersons-images-ca")

# Rekognition Configuration
COLLECTION_ID = os.environ.get("COLLECTION_ID", "famouspersons")

# DynamoDB Tables
PROFILES_TABLE = "profiles"
DETECTED_FACES_TABLE = "detected_faces"
FACE_RECOGNITION_TABLE = os.environ.get("DYNAMODB_TABLE", "facerecognition")

# API Configuration
API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("API_PORT", "8000"))