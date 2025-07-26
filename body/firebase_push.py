import firebase_admin
from firebase_admin import credentials, storage
import json
from google.cloud.storage import Client

# Initialize Firebase with your service account key
cred = credentials.Certificate("cash-snap-467012-firebase-adminsdk-fbsvc-b1230ee713.json")
firebase_admin.initialize_app(cred, {
    'storageBucket': 'cash-snap-467012.firebasestorage.app'
})

# Function to upload JSON file
def upload_json_file(data, file_name):
    bucket = storage.bucket()
    json_data = json.dumps(data).encode('utf-8')
    blob = bucket.blob(f'jsonFiles/{file_name}')
    blob.upload_from_string(json_data, content_type='application/json')
    print(f'File {file_name} uploaded to {blob.public_url}.')
    return blob.public_url

# Function to retrieve JSON file
def get_json_file(file_name):
    bucket = storage.bucket()
    blob = bucket.blob(f'jsonFiles/{file_name}')
    try:
        content = blob.download_as_text()
        json_data = json.loads(content)
        print(f'Retrieved JSON from {file_name}:', json_data)
        return json_data
    except Exception as e:
        print(f'Error retrieving file {file_name}:', e)
        return None

# Example usage
if __name__ == "__main__":
    # Sample JSON data
    sample_data = {
        "name": "example",
        "value": 123,
        "timestamp": "2025-07-26 17:27:00"
    }
    
    # Upload the JSON file
    upload_url = upload_json_file(sample_data, "data.json")
    
    # Retrieve the JSON file
    retrieved_data = get_json_file("data.json")