import firebase_admin
from firebase_admin import credentials, storage
import json

# Initialize Firebase with your service account key
cred = credentials.Certificate("cash-snap-467012-firebase-adminsdk-fbsvc-b1230ee713.json")
firebase_admin.initialize_app(cred, {
    'storageBucket': 'cash-snap-467012.firebasestorage.app'
})


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
    # Retrieve the JSON file
    retrieved_data = get_json_file("data.json")