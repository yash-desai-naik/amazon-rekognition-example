import boto3
import time
import os

from dotenv import load_dotenv

load_dotenv(override=True)

# Configuration
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
PROFILES_TABLE = "profiles"
DETECTED_FACES_TABLE = "detected_faces"
FACE_RECOGNITION_TABLE = os.environ.get("DYNAMODB_TABLE", "facerecognition")

def create_tables_with_retry(max_retries=3):
    """Create DynamoDB tables with retry logic"""
    dynamodb = boto3.client('dynamodb', region_name=AWS_REGION)
    
    # Define table schemas
    table_definitions = {
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
    
    # Check existing tables
    existing_tables = dynamodb.list_tables()['TableNames']
    print(f"Existing tables: {existing_tables}")
    
    # Create tables that don't exist
    for table_name, definition in table_definitions.items():
        if table_name in existing_tables:
            print(f"Table {table_name} already exists.")
            continue
        
        for attempt in range(max_retries):
            try:
                print(f"Creating table {table_name} (attempt {attempt+1})...")
                
                dynamodb.create_table(
                    TableName=table_name,
                    KeySchema=definition["KeySchema"],
                    AttributeDefinitions=definition["AttributeDefinitions"],
                    ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
                )
                
                # Wait for table to be created
                print(f"Waiting for table {table_name} to be created...")
                waiter = dynamodb.get_waiter('table_exists')
                waiter.wait(TableName=table_name)
                
                print(f"Successfully created table {table_name}!")
                break
            except dynamodb.exceptions.ResourceInUseException:
                print(f"Table {table_name} is already being created.")
                break
            except Exception as e:
                print(f"Error creating table {table_name}: {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print(f"Failed to create table {table_name} after {max_retries} attempts.")
    
    # Verify all tables are active
    tables_to_check = list(table_definitions.keys())
    
    # Give tables time to transition to ACTIVE state
    print("Waiting for tables to become active...")
    time.sleep(5)
    
    for table_name in tables_to_check:
        try:
            response = dynamodb.describe_table(TableName=table_name)
            status = response['Table']['TableStatus']
            print(f"Table {table_name} status: {status}")
        except Exception as e:
            print(f"Error checking table {table_name}: {e}")

def create_rekognition_collection():
    """Create Rekognition collection if it doesn't exist"""
    rekognition = boto3.client('rekognition', region_name=AWS_REGION)
    COLLECTION_ID = os.environ.get("COLLECTION_ID", "famouspersons")
    
    try:
        rekognition.describe_collection(CollectionId=COLLECTION_ID)
        print(f"Rekognition collection {COLLECTION_ID} already exists")
    except rekognition.exceptions.ResourceNotFoundException:
        try:
            rekognition.create_collection(CollectionId=COLLECTION_ID)
            print(f"Created Rekognition collection: {COLLECTION_ID}")
        except Exception as e:
            print(f"Error creating Rekognition collection: {e}")

if __name__ == "__main__":
    print("\n=== Creating DynamoDB Tables and Rekognition Collection ===\n")
    
    create_tables_with_retry()
    create_rekognition_collection()
    
    print("\n=== Setup Complete ===\n")
    print("You can now run the FastAPI application with:")
    print("uvicorn main:app --reload")