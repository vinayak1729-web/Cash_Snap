# This MUST be the very first line of your app.py file
from dotenv import load_dotenv
load_dotenv()

"""
Copyright 2022 Google Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import os
import json
import re
import jwt
import requests
from flask import Flask, request, render_template_string
from google.auth.transport.requests import Request
from google.oauth2 import service_account

# TODO: Define Issuer ID - Make sure this is your actual Issuer ID from Google Wallet API console
ISSUER_ID = '3388000000022959328'

# TODO: Define Class ID - This should be unique to your class
CLASS_ID = f'{ISSUER_ID}.codelab_class'

BASE_URL = 'https://walletobjects.googleapis.com/walletobjects/v1'

# --- Debugging line added ---
print('Attempting to load credentials from:', os.getenv('GOOGLE_APPLICATION_CREDENTIALS'))
# --- End Debugging line ---

# Load service account credentials
credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
if not credentials_path:
    raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable not set")

# Load credentials from the JSON file
with open(credentials_path, 'r') as f:
    credentials_info = json.load(f)

credentials = service_account.Credentials.from_service_account_info(
    credentials_info,
    scopes=['https://www.googleapis.com/auth/wallet_object.issuer']
)

app = Flask(__name__)

def get_authenticated_session():
    """Get an authenticated HTTP session for making API requests"""
    credentials.refresh(Request())
    session = requests.Session()
    session.headers.update({
        'Authorization': f'Bearer {credentials.token}',
        'Content-Type': 'application/json'
    })
    return session

async def create_pass_class():
    """
    Creates a sample pass class based on the template defined below.
    
    This class contains multiple editable fields that showcase how to
    customize your class.
    """
    print('create_pass_class called.')
    
    # Define the Generic pass class
    generic_class = {
        'id': CLASS_ID,
        'classTemplateInfo': {
            'cardTemplateOverride': {
                'cardRowTemplateInfos': [
                    {
                        'twoItems': {
                            'startItem': {
                                'firstValue': {
                                    'fields': [
                                        {
                                            'fieldPath': 'object.textModulesData["points"]'
                                        }
                                    ]
                                }
                            },
                            'endItem': {
                                'firstValue': {
                                    'fields': [
                                        {
                                            'fieldPath': 'object.textModulesData["contacts"]'
                                        }
                                    ]
                                }
                            }
                        }
                    }
                ]
            },
            'detailsTemplateOverride': {
                'detailsItemInfos': [
                    {
                        'item': {
                            'firstValue': {
                                'fields': [
                                    {
                                        'fieldPath': 'class.imageModulesData["event_banner"]'
                                    }
                                ]
                            }
                        }
                    },
                    {
                        'item': {
                            'firstValue': {
                                'fields': [
                                    {
                                        'fieldPath': 'class.textModulesData["game_overview"]'
                                    }
                                ]
                            }
                        }
                    },
                    {
                        'item': {
                            'firstValue': {
                                'fields': [
                                    {
                                        'fieldPath': 'class.linksModuleData.uris["official_site"]'
                                    }
                                ]
                            }
                        }
                    }
                ]
            }
        },
        'imageModulesData': [
            {
                'mainImage': {
                    'sourceUri': {
                        'uri': 'https://storage.googleapis.com/wallet-lab-tools-codelab-artifacts-public/google-io-2021-card.png'
                    },
                    'contentDescription': {
                        'defaultValue': {
                            'language': 'en-US',
                            'value': 'Google I/O 2022 Banner'
                        }
                    }
                },
                'id': 'event_banner'
            }
        ],
        'textModulesData': [
            {
                'header': 'Gather points meeting new people at Google I/O',
                'body': 'Join the game and accumulate points in this badge by meeting other attendees in the event.',
                'id': 'game_overview'
            }
        ],
        'linksModuleData': {
            'uris': [
                {
                    'uri': 'https://io.google/2022/',
                    'description': 'Official I/O \'22 Site',
                    'id': 'official_site'
                }
            ]
        }
    }

    session = get_authenticated_session()
    
    try:
        # Check if the class exists already
        response = session.get(f'{BASE_URL}/genericClass/{CLASS_ID}')
        
        if response.status_code == 200:
            print('Class already exists')
            print(response.json())
        else:
            response.raise_for_status()
            
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            # Class does not exist, create it now
            response = session.post(
                f'{BASE_URL}/genericClass',
                json=generic_class
            )
            
            if response.status_code in [200, 201]:
                print('Class insert response')
                print(response.json())
            else:
                print(f'Error creating class: {response.status_code} - {response.text}')
                response.raise_for_status()
        else:
            # Something else went wrong
            print(f'Error: {e}')
            raise e

def create_pass_object(email, class_id):
    """
    Creates a sample pass object based on a given class.
    
    Args:
        email: User's email address
        class_id: The identifier of the parent class used to create the object
        
    Returns:
        HTML response with "Add to Google Wallet" button
    """
    print('create_pass_object called.')
    
    # Create unique object ID using email
    object_suffix = re.sub(r'[^\w.-]', '_', email)
    object_id = f'{ISSUER_ID}.{object_suffix}'
    
    # Define the Generic pass object
    generic_object = {
        'id': object_id,
        'classId': class_id,
        'genericType': 'GENERIC_TYPE_UNSPECIFIED',
        'hexBackgroundColor': '#4285f4',
        'logo': {
            'sourceUri': {
                'uri': 'https://storage.googleapis.com/wallet-lab-tools-codelab-artifacts-public/pass_google_logo.jpg'
            }
        },
        'cardTitle': {
            'defaultValue': {
                'language': 'en',
                'value': 'Google I/O \'22'
            }
        },
        'subheader': {
            'defaultValue': {
                'language': 'en',
                'value': 'Attendee'
            }
        },
        'header': {
            'defaultValue': {
                'language': 'en',
                'value': 'Alex McJacobs'
            }
        },
        'barcode': {
            'type': 'QR_CODE',
            'value': object_id
        },
        'heroImage': {
            'sourceUri': {
                'uri': 'https://storage.googleapis.com/wallet-lab-tools-codelab-artifacts-public/google-io-hero-demo-only.jpg'
            }
        },
        'textModulesData': [
            {
                'header': 'POINTS',
                'body': '1234',
                'id': 'points'
            },
            {
                'header': 'CONTACTS',
                'body': '20',
                'id': 'contacts'
            }
        ]
    }
    
    # Save the pass object to Google Wallet API
    session = get_authenticated_session()
    
    try:
        # Check if the object already exists
        response = session.get(f'{BASE_URL}/genericObject/{object_id}')
        
        if response.status_code == 200:
            print('Object already exists:', response.json())
        else:
            response.raise_for_status()
            
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            # Object does not exist, create it
            response = session.post(
                f'{BASE_URL}/genericObject',
                json=generic_object
            )
            
            if response.status_code in [200, 201]:
                print('Object insert response:', response.json())
            else:
                print(f'Error creating object: {response.status_code} - {response.text}')
                return f'Something went wrong...check the console logs! Status: {response.status_code}'
        else:
            print(f'Error checking/creating object: {e}')
            return 'Something went wrong...check the console logs!'
    
    # Create the signed JWT for the "Add to Google Wallet" button
    claims = {
        'iss': credentials_info['client_email'],
        'aud': 'google',
        'origins': ['http://localhost:5000'],  # Replace with your app's origin
        'typ': 'savetowallet',
        'payload': {
            'genericObjects': [generic_object]
        }
    }
    
    try:
        # Sign the JWT using the service account private key
        token = jwt.encode(claims, credentials_info['private_key'], algorithm='RS256')
        
        # Handle string/bytes difference in different PyJWT versions
        if isinstance(token, bytes):
            token = token.decode('utf-8')
            
        save_url = f'https://pay.google.com/gp/v/save/{token}'
        
        # Return the "Add to Google Wallet" button
        html_template = """
        <html>
            <body>
                <h2>Pass Created Successfully!</h2>
                <p>Click the button below to add your pass to Google Wallet:</p>
                <a href="{{ save_url }}">
                    <img src="https://developers.google.com/wallet/images/add-to-google-wallet/wallet-button.png" alt="Add to Google Wallet">
                </a>
            </body>
        </html>
        """
        
        return render_template_string(html_template, save_url=save_url)
        
    except Exception as error:
        print(f'Error creating JWT: {error}')
        return 'Error generating Add to Google Wallet button...check the console logs!'

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        # Serve a simple form for email input
        form_html = """
        <html>
            <body>
                <h2>Google Wallet Pass Generator</h2>
                <form method="POST">
                    <label for="email">Email:</label><br>
                    <input type="email" id="email" name="email" required><br><br>
                    <input type="submit" value="Create Pass">
                </form>
            </body>
        </html>
        """
        return form_html
    
    elif request.method == 'POST':
        email = request.form.get('email')
        if not email:
            return 'Email is required', 400
            
        # Create pass class (will check if exists first)
        try:
            create_pass_class()  # Note: This is now synchronous
            return create_pass_object(email, CLASS_ID)
        except Exception as e:
            print(f'Error: {e}')
            return 'Something went wrong...check the console logs!', 500

if __name__ == '__main__':
    print('Server listening on port 5000')
    print('Access the application at http://localhost:5000')
    app.run(debug=True, port=5000)