from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Body
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import boto3
import os
import io
from PIL import Image
import uuid
from typing import List, Dict, Optional
from pydantic import BaseModel

app = FastAPI(
    title="Face Recognition API",
    description="API for facial recognition using AWS Rekognition",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Get AWS credentials from environment variables
AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# AWS Service clients
s3 = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION
)
rekognition = boto3.client(
    'rekognition',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION
)
dynamodb = boto3.client(
    'dynamodb',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION
)

# Configuration
S3_BUCKET = os.environ.get("S3_BUCKET", "famouspersons-images-ca")
COLLECTION_ID = os.environ.get("COLLECTION_ID", "famouspersons")
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "face_recognition")

# Verify DynamoDB table exists (helpful for debugging)
try:
    table_check = dynamodb.describe_table(TableName=DYNAMODB_TABLE)
    print(f"DynamoDB table '{DYNAMODB_TABLE}' exists in region {AWS_REGION}")
except Exception as e:
    print(f"WARNING: DynamoDB table check failed: {str(e)}")
    print(f"Make sure table '{DYNAMODB_TABLE}' exists in region {AWS_REGION}")

# Pydantic models for responses
class HealthResponse(BaseModel):
    status: str

class FaceResult(BaseModel):
    face_id: str
    name: str
    confidence: float

class RecognizeResponse(BaseModel):
    results: List[FaceResult]
    count: int

class UploadResponse(BaseModel):
    message: str
    face_id: str
    full_name: str

class ErrorResponse(BaseModel):
    error: str

# New models for group photo handling
class DetectedFace(BaseModel):
    face_id: str
    bounding_box: Dict[str, float]
    confidence: float

class DetectFacesResponse(BaseModel):
    image_id: str
    face_count: int
    faces: List[DetectedFace]

class FaceNameMapping(BaseModel):
    face_id: str
    name: str

class NameFacesRequest(BaseModel):
    image_id: str
    face_mappings: List[FaceNameMapping]

class NameFacesResponse(BaseModel):
    success: bool
    named_faces: int

class GroupPhotoDetails(BaseModel):
    image_id: str
    face_count: int
    named_faces: List[Dict[str, str]]

@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint"""
    return {"status": "Welcome to Face Recognition API"}

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.post("/upload", response_model=UploadResponse, responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def upload_face(
    image: UploadFile = File(...),
    name: str = Form(...)
):
    """
    Upload a face image with person name
    
    - **image**: Image file containing a face
    - **name**: Full name of the person
    
    Returns the face ID and confirmation message
    """
    if not image.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    try:
        # Read file contents
        contents = await image.read()
        
        # Generate a unique filename
        filename = str(uuid.uuid4()) + os.path.splitext(image.filename)[1]
        file_path = f"index/{filename}"
        
        # Upload to S3 with metadata
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=file_path,
            Body=contents,
            Metadata={'fullname': name}
        )
        
        # Index face with Amazon Rekognition
        response = rekognition.index_faces(
            Image={
                "S3Object": {
                    "Bucket": S3_BUCKET,
                    "Name": file_path
                }
            },
            CollectionId=COLLECTION_ID
        )
        
        # Store face ID and full name in DynamoDB
        if response['ResponseMetadata']['HTTPStatusCode'] == 200 and response['FaceRecords']:
            face_id = response['FaceRecords'][0]['Face']['FaceId']
            
            dynamodb.put_item(
                TableName=DYNAMODB_TABLE,
                Item={
                    'RekognitionId': {'S': face_id},
                    'FullName': {'S': name}
                }
            )
            
            return {
                "message": "Face indexed successfully",
                "face_id": face_id,
                "full_name": name
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to index face")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/recognize", response_model=RecognizeResponse, responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def recognize_face(
    image: UploadFile = File(...)
):
    """
    Recognize a face from uploaded image
    
    - **image**: Image file containing a face to recognize
    
    Returns a list of matching faces with confidence scores
    """
    if not image.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    try:
        # Read file contents
        contents = await image.read()
        
        # Process the image
        image_obj = Image.open(io.BytesIO(contents))
        stream = io.BytesIO()
        image_obj.save(stream, format="JPEG")
        image_binary = stream.getvalue()
        
        # Search for matching faces
        response = rekognition.search_faces_by_image(
            CollectionId=COLLECTION_ID,
            Image={'Bytes': image_binary},
            MaxFaces=5,
            FaceMatchThreshold=80
        )
        
        results = []
        for match in response['FaceMatches']:
            face_id = match['Face']['FaceId']
            confidence = match['Face']['Confidence']
            
            # Get person name from DynamoDB
            face_data = dynamodb.get_item(
                TableName=DYNAMODB_TABLE,
                Key={'RekognitionId': {'S': face_id}}
            )
            
            person_name = face_data.get('Item', {}).get('FullName', {}).get('S', 'Unknown')
            
            results.append({
                "face_id": face_id,
                "name": person_name,
                "confidence": confidence
            })
        
        return {
            "results": results,
            "count": len(results)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/faces", responses={500: {"model": ErrorResponse}})
async def list_faces():
    """
    List all indexed faces in the collection
    
    Returns all faces with their IDs and names
    """
    try:
        # Scan the DynamoDB table
        response = dynamodb.scan(
            TableName=DYNAMODB_TABLE,
            FilterExpression="attribute_not_exists(SourceImageId) AND attribute_not_exists(FaceCount)"
        )
        
        faces = []
        for item in response.get('Items', []):
            face_id = item.get('RekognitionId', {}).get('S')
            # Skip group photo entries
            if face_id and not face_id.startswith('IMG_'):
                faces.append({
                    "face_id": face_id,
                    "name": item.get('FullName', {}).get('S')
                })
        
        return {
            "faces": faces,
            "count": len(faces)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/faces/{face_id}", responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def delete_face(face_id: str):
    """
    Delete a face from the collection
    
    - **face_id**: ID of the face to delete
    
    Returns confirmation of deletion
    """
    try:
        # Check if face exists
        face_data = dynamodb.get_item(
            TableName=DYNAMODB_TABLE,
            Key={'RekognitionId': {'S': face_id}}
        )
        
        if 'Item' not in face_data:
            raise HTTPException(status_code=404, detail="Face not found")
        
        # Delete from Rekognition collection
        rekognition.delete_faces(
            CollectionId=COLLECTION_ID,
            FaceIds=[face_id]
        )
        
        # Delete from DynamoDB
        dynamodb.delete_item(
            TableName=DYNAMODB_TABLE,
            Key={'RekognitionId': {'S': face_id}}
        )
        
        return {
            "message": "Face deleted successfully",
            "face_id": face_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# New endpoints for group photo handling
@app.post("/detect-faces", response_model=DetectFacesResponse, responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def detect_faces(
    image: UploadFile = File(...)
):
    """
    Detect faces in a group photo without identifying them
    
    - **image**: Group photo with multiple faces
    
    Returns face IDs and their locations that can be named later
    """
    if not image.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    
    try:
        # Read file contents
        contents = await image.read()
        
        # Generate a unique ID for this image
        image_id = str(uuid.uuid4())
        file_path = f"group/{image_id}{os.path.splitext(image.filename)[1]}"
        
        # Upload to S3
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=file_path,
            Body=contents
        )
        
        # Detect faces with Amazon Rekognition
        response = rekognition.index_faces(
            Image={
                "S3Object": {
                    "Bucket": S3_BUCKET,
                    "Name": file_path
                }
            },
            CollectionId=COLLECTION_ID,
            DetectionAttributes=['DEFAULT'],
            MaxFaces=100  # Adjust as needed
        )
        
        # Extract face data
        faces = []
        for face_record in response.get('FaceRecords', []):
            face = face_record.get('Face', {})
            faces.append(
                DetectedFace(
                    face_id=face.get('FaceId', ''),
                    bounding_box=face.get('BoundingBox', {}),
                    confidence=face.get('Confidence', 0.0)
                )
            )
        
        # Store image ID and path in DynamoDB for reference
        dynamodb.put_item(
            TableName=DYNAMODB_TABLE,
            Item={
                'RekognitionId': {'S': f"IMG_{image_id}"},
                'FullName': {'S': "GROUP_PHOTO"},
                'ImagePath': {'S': file_path},
                'FaceCount': {'N': str(len(faces))}
            }
        )
        
        return {
            "image_id": image_id,
            "face_count": len(faces),
            "faces": faces
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/name-faces", response_model=NameFacesResponse, responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def name_faces(
    request: NameFacesRequest
):
    """
    Assign names to previously detected faces
    
    - **image_id**: ID of the previously uploaded group photo
    - **face_mappings**: List of face IDs and corresponding names
    
    Returns confirmation of named faces
    """
    try:
        # Get image reference
        image_record = dynamodb.get_item(
            TableName=DYNAMODB_TABLE,
            Key={'RekognitionId': {'S': f"IMG_{request.image_id}"}}
        )
        
        if 'Item' not in image_record:
            raise HTTPException(
                status_code=404, 
                detail=f"Image with ID {request.image_id} not found"
            )
        
        # Update names for each face ID
        for mapping in request.face_mappings:
            if not mapping.name:
                continue  # Skip empty names
                
            dynamodb.put_item(
                TableName=DYNAMODB_TABLE,
                Item={
                    'RekognitionId': {'S': mapping.face_id},
                    'FullName': {'S': mapping.name},
                    'SourceImageId': {'S': request.image_id}
                }
            )
        
        return {
            "success": True,
            "named_faces": len(request.face_mappings)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/group-photos", responses={500: {"model": ErrorResponse}})
async def list_group_photos():
    """
    List all uploaded group photos
    
    Returns basic information about all group photos
    """
    try:
        # Scan the DynamoDB table for group photos
        response = dynamodb.scan(
            TableName=DYNAMODB_TABLE,
            FilterExpression="begins_with(RekognitionId, :prefix)",
            ExpressionAttributeValues={
                ":prefix": {"S": "IMG_"}
            }
        )
        
        photos = []
        for item in response.get('Items', []):
            image_id = item.get('RekognitionId', {}).get('S', '')[4:]  # Remove 'IMG_' prefix
            face_count = item.get('FaceCount', {}).get('N', '0')
            image_path = item.get('ImagePath', {}).get('S', '')
            
            photos.append({
                "image_id": image_id,
                "face_count": int(face_count),
                "image_path": image_path
            })
        
        return {
            "photos": photos,
            "count": len(photos)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/group-photos/{image_id}", response_model=GroupPhotoDetails, responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def get_group_photo_details(image_id: str):
    """
    Get details of a previously uploaded group photo
    
    - **image_id**: ID of the group photo
    
    Returns the faces detected and their assigned names (if any)
    """
    try:
        # Get image reference
        image_record = dynamodb.get_item(
            TableName=DYNAMODB_TABLE,
            Key={'RekognitionId': {'S': f"IMG_{image_id}"}}
        )
        
        if 'Item' not in image_record:
            raise HTTPException(
                status_code=404, 
                detail=f"Image with ID {image_id} not found"
            )
            
        # Get all faces from this image
        # For a real app, you should use a secondary index in DynamoDB
        # This is a simplified implementation
        scan_response = dynamodb.scan(
            TableName=DYNAMODB_TABLE,
            FilterExpression="attribute_exists(SourceImageId) AND SourceImageId = :id",
            ExpressionAttributeValues={
                ":id": {"S": image_id}
            }
        )
        
        named_faces = []
        for item in scan_response.get('Items', []):
            named_faces.append({
                "face_id": item.get('RekognitionId', {}).get('S', ''),
                "name": item.get('FullName', {}).get('S', '')
            })
        
        return {
            "image_id": image_id,
            "face_count": int(image_record['Item'].get('FaceCount', {}).get('N', '0')),
            "named_faces": named_faces
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))