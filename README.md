# Commands

Video Link: [https://youtu.be/oHSesteFK5c](https://youtu.be/oHSesteFK5c)


- Install aws-shell
```
pip install aws-shell
```

- Configure
```
aws configure
```

- Create a collection on aws rekognition
```
aws rekognition create-collection --collection-id facerecognition_collection --region us-east-1
```

- Create table on DynamoDB
```
aws dynamodb create-table --table-name facerecognition \
--attribute-definitions AttributeName=RekognitionId,AttributeType=S \
--key-schema AttributeName=RekognitionId,KeyType=HASH \
--provisioned-throughput ReadCapacityUnits=1,WriteCapacityUnits=1 \
--region us-east-1
```

- Create S3 bucket
```
aws s3 mb s3://bucket-name --region us-east-1
```


---
# Face Recognition API

A FastAPI application for facial recognition using AWS Rekognition, S3, and DynamoDB.

## Prerequisites

- Python 3.8+
- AWS account with configured credentials
- S3 bucket named 'famouspersons-images-ca'
- DynamoDB table named 'face_recognition'
- Rekognition collection named 'famouspersons'

## Installation

1. Clone this repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure AWS credentials:

```bash
aws configure
```

Or set environment variables:

```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=your_region
```

## Usage

1. Start the API server:

```bash
uvicorn app:app --reload
```

2. Access the API documentation at http://localhost:8000/docs

## API Endpoints

### Health Check
```
GET /health
```

### Upload a Face
```
POST /upload
Form data:
- image: Image file
- name: Full name of the person
```

### Recognize a Face
```
POST /recognize
Form data:
- image: Image file
```

### List All Faces
```
GET /faces
```

### Delete a Face
```
DELETE /faces/{face_id}
```

## AWS Setup Notes

1. Make sure your IAM policy includes permissions for:
   - S3 (GetObject, PutObject)
   - DynamoDB (PutItem, GetItem, Scan, DeleteItem)
   - Rekognition (IndexFaces, SearchFacesByImage, DeleteFaces)

2. The DynamoDB table should have 'RekognitionId' as the primary key

## License

MIT