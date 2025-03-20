from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import boto3
from decimal import Decimal
import io
import uuid
from datetime import datetime
from PIL import Image
from typing import List, Optional
from pydantic import BaseModel, Field
import os
import logging
import json

from dotenv import load_dotenv

load_dotenv(override=True)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api.index")

# Config
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
S3_BUCKET = os.environ.get("S3_BUCKET", "famouspersons-images-ca")
COLLECTION_ID = os.environ.get("COLLECTION_ID", "famouspersons")
PROFILES_TABLE = "profiles"
DETECTED_FACES_TABLE = "detected_faces"
FACE_RECOGNITION_TABLE = os.environ.get("DYNAMODB_TABLE", "facerecognition")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# AWS clients
s3 = boto3.client('s3', region_name=AWS_REGION)
rekognition = boto3.client('rekognition', region_name=AWS_REGION)
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)

# Data models
class ProfileCreate(BaseModel):
    name: str

class Profile(BaseModel):
    profile_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    face_id: Optional[str] = None
    profile_image_s3: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

class DetectedFace(BaseModel):
    detected_face_id: str
    image_id: str
    s3_path: str
    matched_profile_id: Optional[str] = None
    bounding_box: dict
    confidence: Optional[float] = None
    timestamp: str

class ProfileResponse(Profile):
    matched_images: List[str] = []

class DetectedFaceResponse(DetectedFace):
    pass

def create_dynamodb_tables():
    """Create required DynamoDB tables if they don't exist"""
    dynamodb_client = boto3.client('dynamodb', region_name=AWS_REGION)
    
    # Define table schemas
    tables = {
        PROFILES_TABLE: {
            "KeySchema": [{'AttributeName': 'profile_id', 'KeyType': 'HASH'}],
            "AttributeDefinitions": [{'AttributeName': 'profile_id', 'AttributeType': 'S'}]
        },
        DETECTED_FACES_TABLE: {
            "KeySchema": [
                {'AttributeName': 'detected_face_id', 'KeyType': 'HASH'},
                {'AttributeName': 'image_id', 'KeyType': 'RANGE'}
            ],
            "AttributeDefinitions": [
                {'AttributeName': 'detected_face_id', 'AttributeType': 'S'},
                {'AttributeName': 'image_id', 'AttributeType': 'S'}
            ]
        },
        FACE_RECOGNITION_TABLE: {
            "KeySchema": [{'AttributeName': 'RekognitionId', 'KeyType': 'HASH'}],
            "AttributeDefinitions": [{'AttributeName': 'RekognitionId', 'AttributeType': 'S'}]
        }
    }
    
    # Create tables that don't exist
    for table_name, schema in tables.items():
        try:
            # Check if table exists
            dynamodb_client.describe_table(TableName=table_name)
            logger.info(f"Table {table_name} already exists")
        except dynamodb_client.exceptions.ResourceNotFoundException:
            try:
                logger.info(f"Creating table {table_name}...")
                dynamodb_client.create_table(
                    TableName=table_name,
                    KeySchema=schema["KeySchema"],
                    AttributeDefinitions=schema["AttributeDefinitions"],
                    ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
                )
                # Wait for table to be created
                waiter = dynamodb_client.get_waiter('table_exists')
                waiter.wait(TableName=table_name)
                logger.info(f"Created table {table_name}")
            except Exception as e:
                logger.error(f"Error creating table {table_name}: {e}")

def create_rekognition_collection():
    """Create Rekognition collection if it doesn't exist"""
    try:
        rekognition.describe_collection(CollectionId=COLLECTION_ID)
        logger.info(f"Rekognition collection {COLLECTION_ID} already exists")
    except rekognition.exceptions.ResourceNotFoundException:
        try:
            rekognition.create_collection(CollectionId=COLLECTION_ID)
            logger.info(f"Created Rekognition collection {COLLECTION_ID}")
        except Exception as e:
            logger.error(f"Error creating Rekognition collection: {e}")

def get_s3_presigned_url(s3_uri, expiration=3600):
    """Generate a pre-signed URL for S3 object"""
    if not s3_uri or not s3_uri.startswith("s3://"):
        return s3_uri
    
    bucket_key = s3_uri.replace("s3://", "").split("/", 1)
    if len(bucket_key) != 2:
        return s3_uri
    
    bucket, key = bucket_key
    
    try:
        url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=expiration
        )
        return url
    except Exception as e:
        logger.error(f"Error generating presigned URL: {e}")
        return s3_uri

@app.on_event("startup")
async def startup():
    """Initialize resources on startup"""
    create_rekognition_collection()
    create_dynamodb_tables()

@app.get("/")
async def root():
    return {"message": "Face Recognition API is running"}

@app.post("/upload_image", response_model=List[DetectedFaceResponse])
async def upload_image(file: UploadFile = File(...), description: str = Form(None)):
    """Upload a group image and detect faces"""
    try:
        # Read image and upload to S3
        image_content = await file.read()
        image_id = str(uuid.uuid4())
        s3_key = f"groups/{image_id}.jpg"
        
        s3.upload_fileobj(io.BytesIO(image_content), S3_BUCKET, s3_key)
        s3_uri = f"s3://{S3_BUCKET}/{s3_key}"
        logger.info(f"Uploaded image to S3: {s3_uri}")
        
        # Detect faces
        response = rekognition.detect_faces(
            Image={'S3Object': {'Bucket': S3_BUCKET, 'Name': s3_key}},
            Attributes=['DEFAULT']
        )
        logger.info(f"Detected {len(response['FaceDetails'])} faces")
        
        results = []
        faces_table = dynamodb.Table(DETECTED_FACES_TABLE)
        
        for face_detail in response['FaceDetails']:
            try:
                # Index face in collection
                index_response = rekognition.index_faces(
                    CollectionId=COLLECTION_ID,
                    Image={'S3Object': {'Bucket': S3_BUCKET, 'Name': s3_key}},
                    MaxFaces=1,
                    DetectionAttributes=['DEFAULT']
                )
                
                if not index_response['FaceRecords']:
                    continue
                
                face_id = index_response['FaceRecords'][0]['Face']['FaceId']
                
                # Search for matching profiles
                match_response = rekognition.search_faces(
                    CollectionId=COLLECTION_ID,
                    FaceId=face_id,
                    MaxFaces=1,
                    FaceMatchThreshold=90.0
                )
                
                matched_profile_id = None
                confidence = None
                
                if match_response['FaceMatches']:
                    match = match_response['FaceMatches'][0]
                    matched_face_id = match['Face']['FaceId']
                    
                    # Check if matched face belongs to a profile
                    profiles_table = dynamodb.Table(PROFILES_TABLE)
                    profile_response = profiles_table.scan(
                        FilterExpression="face_id = :face_id",
                        ExpressionAttributeValues={":face_id": matched_face_id}
                    )
                    
                    if profile_response['Items']:
                        matched_profile_id = profile_response['Items'][0]['profile_id']
                        confidence = float(match['Similarity'])
                
                # Store face data in DynamoDB
                timestamp = datetime.now().isoformat()
                
                # Convert floats to Decimal for DynamoDB
                bounding_box = {}
                for key, value in face_detail['BoundingBox'].items():
                    bounding_box[key] = Decimal(str(value))
                
                face_item = {
                    'detected_face_id': face_id,
                    'image_id': image_id,
                    's3_path': s3_uri,
                    'bounding_box': bounding_box,
                    'timestamp': timestamp
                }
                
                if matched_profile_id:
                    face_item['matched_profile_id'] = matched_profile_id
                
                if confidence:
                    face_item['confidence'] = Decimal(str(confidence))
                
                faces_table.put_item(Item=face_item)
                
                # Create response object with HTTPS URL
                face_response = DetectedFaceResponse(
                    detected_face_id=face_id,
                    image_id=image_id,
                    s3_path=get_s3_presigned_url(s3_uri),
                    matched_profile_id=matched_profile_id,
                    bounding_box=face_detail['BoundingBox'],
                    confidence=confidence,
                    timestamp=timestamp
                )
                
                results.append(face_response)
            
            except Exception as e:
                logger.error(f"Error processing face: {e}")
        
        return results
    
    except Exception as e:
        logger.error(f"Error in upload_image: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/profiles", response_model=ProfileResponse)
async def create_profile(name: str = Form(...), file: UploadFile = File(...)):
    """Create a profile with a reference face image"""
    try:
        # Read image and upload to S3
        image_content = await file.read()
        profile_id = str(uuid.uuid4())
        s3_key = f"profiles/{profile_id}.jpg"
        
        s3.upload_fileobj(io.BytesIO(image_content), S3_BUCKET, s3_key)
        s3_uri = f"s3://{S3_BUCKET}/{s3_key}"
        logger.info(f"Uploaded profile image to S3: {s3_uri}")
        
        # Index face
        index_response = rekognition.index_faces(
            CollectionId=COLLECTION_ID,
            Image={'S3Object': {'Bucket': S3_BUCKET, 'Name': s3_key}},
            MaxFaces=1,
            DetectionAttributes=['DEFAULT']
        )
        
        if not index_response['FaceRecords']:
            raise HTTPException(status_code=400, detail="No face detected in the image")
        
        face_id = index_response['FaceRecords'][0]['Face']['FaceId']
        logger.info(f"Indexed face with ID: {face_id}")
        
        # Create profile in DynamoDB
        timestamp = datetime.now().isoformat()
        profile_item = {
            'profile_id': profile_id,
            'name': name,
            'face_id': face_id,
            'profile_image_s3': s3_uri,
            'created_at': timestamp
        }
        
        profiles_table = dynamodb.Table(PROFILES_TABLE)
        profiles_table.put_item(Item=profile_item)
        logger.info(f"Created profile: {profile_id}")
        
        # Match with existing faces
        match_with_detected_faces(face_id, profile_id)
        
        # Get matched images
        matched_images = get_matched_images(profile_id)
        https_matched_images = [get_s3_presigned_url(img) for img in matched_images]
        
        # Return profile response
        return ProfileResponse(
            profile_id=profile_id,
            name=name,
            face_id=face_id,
            profile_image_s3=get_s3_presigned_url(s3_uri),
            created_at=timestamp,
            matched_images=https_matched_images
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/profiles", response_model=List[ProfileResponse])
async def get_profiles():
    """Get all profiles"""
    try:
        profiles_table = dynamodb.Table(PROFILES_TABLE)
        response = profiles_table.scan()
        
        profiles = []
        for item in response.get('Items', []):
            try:
                matched_images = get_matched_images(item['profile_id'])
                https_matched_images = [get_s3_presigned_url(img) for img in matched_images]
                
                profile = ProfileResponse(
                    profile_id=item['profile_id'],
                    name=item['name'],
                    face_id=item['face_id'],
                    profile_image_s3=get_s3_presigned_url(item['profile_image_s3']),
                    created_at=item['created_at'],
                    matched_images=https_matched_images
                )
                profiles.append(profile)
            except Exception as e:
                logger.error(f"Error processing profile {item.get('profile_id')}: {e}")
        
        return profiles
    
    except Exception as e:
        logger.error(f"Error in get_profiles: {e}")
        return []

@app.get("/profiles/{profile_id}", response_model=ProfileResponse)
async def get_profile(profile_id: str):
    """Get a specific profile by ID"""
    try:
        profiles_table = dynamodb.Table(PROFILES_TABLE)
        response = profiles_table.get_item(Key={"profile_id": profile_id})
        
        if not response.get('Item'):
            raise HTTPException(status_code=404, detail="Profile not found")
        
        item = response['Item']
        matched_images = get_matched_images(profile_id)
        https_matched_images = [get_s3_presigned_url(img) for img in matched_images]
        
        return ProfileResponse(
            profile_id=item['profile_id'],
            name=item['name'],
            face_id=item['face_id'],
            profile_image_s3=get_s3_presigned_url(item['profile_image_s3']),
            created_at=item['created_at'],
            matched_images=https_matched_images
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/match_faces/{profile_id}", response_model=ProfileResponse)
async def match_faces(profile_id: str):
    """Force re-matching of a profile with detected faces"""
    try:
        profiles_table = dynamodb.Table(PROFILES_TABLE)
        response = profiles_table.get_item(Key={"profile_id": profile_id})
        
        if not response.get('Item'):
            raise HTTPException(status_code=404, detail="Profile not found")
        
        item = response['Item']
        match_with_detected_faces(item['face_id'], profile_id)
        
        matched_images = get_matched_images(profile_id)
        https_matched_images = [get_s3_presigned_url(img) for img in matched_images]
        
        return ProfileResponse(
            profile_id=item['profile_id'],
            name=item['name'],
            face_id=item['face_id'],
            profile_image_s3=get_s3_presigned_url(item['profile_image_s3']),
            created_at=item['created_at'],
            matched_images=https_matched_images
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in match_faces: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def match_with_detected_faces(face_id: str, profile_id: str):
    """Match a profile face with detected faces"""
    try:
        # Search for matches in the collection
        match_response = rekognition.search_faces(
            CollectionId=COLLECTION_ID,
            FaceId=face_id,
            MaxFaces=100,
            FaceMatchThreshold=80.0
        )
        
        faces_table = dynamodb.Table(DETECTED_FACES_TABLE)
        
        # Update matched faces
        for match in match_response.get('FaceMatches', []):
            matched_face_id = match['Face']['FaceId']
            confidence = Decimal(str(match['Similarity']))
            
            # Find detected faces with this ID
            response = faces_table.scan(
                FilterExpression="detected_face_id = :face_id",
                ExpressionAttributeValues={":face_id": matched_face_id}
            )
            
            for item in response.get('Items', []):
                # Update with matched profile
                faces_table.update_item(
                    Key={
                        "detected_face_id": matched_face_id,
                        "image_id": item['image_id']
                    },
                    UpdateExpression="SET matched_profile_id = :pid, confidence = :conf",
                    ExpressionAttributeValues={
                        ":pid": profile_id,
                        ":conf": confidence
                    }
                )
        
        logger.info(f"Matched profile {profile_id} with {len(match_response.get('FaceMatches', []))} faces")
        return True
    
    except Exception as e:
        logger.error(f"Error in match_with_detected_faces: {e}")
        return False

def get_matched_images(profile_id: str):
    """Get images matched to a profile"""
    try:
        faces_table = dynamodb.Table(DETECTED_FACES_TABLE)
        response = faces_table.scan(
            FilterExpression="matched_profile_id = :pid",
            ExpressionAttributeValues={":pid": profile_id}
        )
        
        # Get unique image paths
        image_paths = set()
        for item in response.get('Items', []):
            if 's3_path' in item:
                image_paths.add(item['s3_path'])
        
        return list(image_paths)
    
    except Exception as e:
        logger.error(f"Error in get_matched_images: {e}")
        return []