import boto3
import os
from dotenv import load_dotenv

load_dotenv(override=True)

# AWS Configuration
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
PROFILES_TABLE = "profiles"
DETECTED_FACES_TABLE = "detected_faces"

def create_tables():
    print("Creating required DynamoDB tables...")
    dynamodb = boto3.client('dynamodb', region_name=AWS_REGION)
    
    # Create profiles table
    try:
        dynamodb.create_table(
            TableName=PROFILES_TABLE,
            KeySchema=[
                {'AttributeName': 'profile_id', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'profile_id', 'AttributeType': 'S'}
            ],
            ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        )
        # Wait for table to be created
        print(f"Waiting for table {PROFILES_TABLE} to be created...")
        waiter = dynamodb.get_waiter('table_exists')
        waiter.wait(TableName=PROFILES_TABLE)
        print(f"Created DynamoDB table: {PROFILES_TABLE}")
    except dynamodb.exceptions.ResourceInUseException:
        print(f"Table {PROFILES_TABLE} already exists")
    
    # Create detected faces table
    try:
        dynamodb.create_table(
            TableName=DETECTED_FACES_TABLE,
            KeySchema=[
                {'AttributeName': 'detected_face_id', 'KeyType': 'HASH'},
                {'AttributeName': 'image_id', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'detected_face_id', 'AttributeType': 'S'},
                {'AttributeName': 'image_id', 'AttributeType': 'S'}
            ],
            ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
        )
        # Wait for table to be created
        print(f"Waiting for table {DETECTED_FACES_TABLE} to be created...")
        waiter = dynamodb.get_waiter('table_exists')
        waiter.wait(TableName=DETECTED_FACES_TABLE)
        print(f"Created DynamoDB table: {DETECTED_FACES_TABLE}")
    except dynamodb.exceptions.ResourceInUseException:
        print(f"Table {DETECTED_FACES_TABLE} already exists")
    
    # Verify tables created successfully
    print("Verifying tables...")
    tables_response = dynamodb.list_tables()
    created_tables = tables_response['TableNames']
    
    if PROFILES_TABLE in created_tables and DETECTED_FACES_TABLE in created_tables:
        print("DynamoDB tables created and verified successfully!")
    else:
        print(f"WARNING: Some tables may not be created. Available tables: {created_tables}")
        
    # Add short delay to ensure tables are fully active
    import time
    time.sleep(5)
    print("Table creation process complete.")

if __name__ == "__main__":
    create_tables()