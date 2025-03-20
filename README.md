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


---# AWS Rekognition Face Recognition System

This project provides a complete face recognition system using AWS Rekognition, with a FastAPI backend and Streamlit frontend.

## Features

- Upload group photos with multiple faces
- Automatically detect and index faces without requiring names during upload
- Label faces with names after upload (batch naming workflow)
- Group faces by person name/ID
- Search for matching faces in new photos
- View all detected faces grouped by person

## Components

1. **FastAPI Backend** - Handles all AWS service interactions
2. **Streamlit Dashboard** - Provides a user-friendly interface
3. **AWS Lambda Function** - Processes S3 uploads automatically
4. **AWS Services Used**:
   - Amazon Rekognition - Face detection and indexing
   - Amazon S3 - Image storage
   - Amazon DynamoDB - Face metadata storage

## Project Structure

```
├── api/
│   └── index.py        # FastAPI application
├── app.py              # Streamlit dashboard
├── lambda_function.py  # AWS Lambda handler
├── vercel.json         # Vercel deployment configuration
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## Setup Instructions

### Prerequisites

- AWS Account with access to:
  - S3
  - DynamoDB
  - Rekognition
  - Lambda
- Python 3.8+
- Vercel account (for hosting the API)

### AWS Setup

1. **Create S3 Bucket**:
   - Create a bucket named `famouspersons-images-ca` (or update the code with your bucket name)
   - Configure CORS settings to allow API access

2. **Create DynamoDB Table**:
   - Table name: `face_recognition`
   - Primary key: `RekognitionId` (String)

3. **Create Rekognition Collection**:
   - Collection ID: `famouspersons`
   ```bash
   aws rekognition create-collection --collection-id famouspersons
   ```

4. **Set up Lambda Function**:
   - Create a new Lambda function
   - Use the provided `lambda_function.py` as the handler
   - Configure S3 bucket to trigger Lambda on object creation
   - Attach IAM policy similar to the provided `policy.json`

### API Setup

1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set environment variables:
   ```bash
   export AWS_ACCESS_KEY_ID=your-access-key
   export AWS_SECRET_ACCESS_KEY=your-secret-key
   export AWS_REGION=your-aws-region
   export S3_BUCKET=famouspersons-images-ca
   ```

4. Deploy to Vercel:
   ```bash
   vercel
   ```

### Streamlit Dashboard Setup

1. Install Streamlit and other requirements:
   ```bash
   pip install -r requirements.txt
   ```

2. Set the API URL environment variable:
   ```bash
   export API_URL=https://your-vercel-deployment-url
   ```

3. Run the Streamlit app:
   ```bash
   streamlit run app.py
   ```

## Usage

### Upload Group Photos

1. Go to the "Upload & Process" tab
2. Upload a group photo
3. Click "Process Image" to detect and index faces

### Label Faces

1. Navigate to the "Label Faces" tab
2. Click "Get Unnamed Faces" to see all unlabeled faces
3. Select an image to work with
4. Enter names for each detected face and click "Save"

### View Grouped Faces

1. Go to the "View Groups" tab
2. Click "Load Grouped Faces" to see all faces grouped by name

### Recognize New Faces

1. Use the sidebar uploader to upload a new image
2. Click "Recognize Faces" to find matches with previously indexed faces

## Customization

- Update environment variables to use different AWS resources
- Modify confidence thresholds in the API code to adjust face detection sensitivity
- Enhance the Streamlit UI by adding more visualization features

## Security Considerations

- This demo uses environment variables for AWS credentials, which is not recommended for production
- For production, use AWS IAM roles and secure credential management
- Implement proper authentication and authorization for the API
- Add validation for user inputs to prevent security issues

## License

[MIT License](LICENSE)