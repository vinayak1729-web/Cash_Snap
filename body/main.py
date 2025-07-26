import streamlit as st
import json
import os
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from PIL import Image
import base64
import io
import google.generativeai as genai
from typing import Dict, List, Optional
import re

# Google Wallet Integration
import jwt
import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

# Configure page
st.set_page_config(
    page_title="Cash Snap AI - Financial Assistant",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Define file paths
JSON_FILE_PATH = os.path.join(os.path.dirname(__file__), 'transactions.json')
USER_PROFILE_PATH = os.path.join(os.path.dirname(__file__), 'user_profile.json')

# Google Wallet Configuration
ISSUER_ID = '3388000000022959328'  # Replace with your actual Issuer ID
CLASS_ID = f'{ISSUER_ID}.cashsnap_receipt_class'
BASE_URL = 'https://walletobjects.googleapis.com/walletobjects/v1'

# Initialize session state
if 'transactions' not in st.session_state:
    st.session_state.transactions = []
if 'user_profile' not in st.session_state:
    st.session_state.user_profile = {}
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'wallet_credentials' not in st.session_state:
    st.session_state.wallet_credentials = None

# Google Wallet Functions
def setup_google_wallet():
    """Setup Google Wallet credentials"""
    st.sidebar.subheader("🏦 Google Wallet Setup")
    
    # Option 1: Upload service account JSON file
    uploaded_file = st.sidebar.file_uploader(
        "Upload Google Service Account JSON",
        type=['json'],
        help="Upload your Google Cloud service account JSON file"
    )
    
    if uploaded_file:
        try:
            credentials_info = json.load(uploaded_file)
            credentials = service_account.Credentials.from_service_account_info(
                credentials_info,
                scopes=['https://www.googleapis.com/auth/wallet_object.issuer']
            )
            st.session_state.wallet_credentials = {
                'credentials': credentials,
                'credentials_info': credentials_info
            }
            st.sidebar.success("✅ Google Wallet credentials loaded!")
            return True
        except Exception as e:
            st.sidebar.error(f"❌ Invalid credentials file: {str(e)}")
            return False
    
    # Option 2: Manual JSON input
    with st.sidebar.expander("Or paste JSON credentials"):
        json_input = st.text_area(
            "Service Account JSON",
            height=100,
            placeholder='{"type": "service_account", "project_id": "...", ...}'
        )
        
        if st.button("Load Credentials") and json_input:
            try:
                credentials_info = json.loads(json_input)
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_info,
                    scopes=['https://www.googleapis.com/auth/wallet_object.issuer']
                )
                st.session_state.wallet_credentials = {
                    'credentials': credentials,
                    'credentials_info': credentials_info
                }
                st.sidebar.success("✅ Google Wallet credentials loaded!")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"❌ Invalid JSON: {str(e)}")
    
    return st.session_state.wallet_credentials is not None

def get_authenticated_session():
    """Get an authenticated HTTP session for making API requests"""
    if not st.session_state.wallet_credentials:
        return None
    
    credentials = st.session_state.wallet_credentials['credentials']
    credentials.refresh(Request())
    session = requests.Session()
    session.headers.update({
        'Authorization': f'Bearer {credentials.token}',
        'Content-Type': 'application/json'
    })
    return session

def create_receipt_pass_class():
    """Create a Google Wallet pass class for receipts"""
    session = get_authenticated_session()
    if not session:
        return False
    
    # Define the receipt pass class
    receipt_class = {
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
                                            'fieldPath': 'object.textModulesData["total_amount"]'
                                        }
                                    ]
                                }
                            },
                            'endItem': {
                                'firstValue': {
                                    'fields': [
                                        {
                                            'fieldPath': 'object.textModulesData["category"]'
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
                                        'fieldPath': 'object.textModulesData["merchant"]'
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
                                        'fieldPath': 'object.textModulesData["transaction_date"]'
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
                                        'fieldPath': 'object.textModulesData["payment_method"]'
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
                        'uri': 'https://storage.googleapis.com/wallet-lab-tools-codelab-artifacts-public/pass_google_logo.jpg'
                    },
                    'contentDescription': {
                        'defaultValue': {
                            'language': 'en-US',
                            'value': 'Cash Snap AI Receipt'
                        }
                    }
                },
                'id': 'receipt_logo'
            }
        ],
        'textModulesData': [
            {
                'header': 'Digital Receipt',
                'body': 'Your transaction receipt stored securely in Google Wallet',
                'id': 'receipt_description'
            }
        ]
    }
    
    try:
        # Check if the class exists already
        response = session.get(f'{BASE_URL}/genericClass/{CLASS_ID}')
        
        if response.status_code == 200:
            return True
        else:
            response.raise_for_status()
            
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            # Class does not exist, create it now
            response = session.post(
                f'{BASE_URL}/genericClass',
                json=receipt_class
            )
            
            if response.status_code in [200, 201]:
                return True
            else:
                st.error(f'Error creating wallet class: {response.status_code} - {response.text}')
                return False
        else:
            st.error(f'Error checking wallet class: {e}')
            return False
    
    return True

def create_receipt_wallet_pass(transaction):
    """Create a Google Wallet pass for a transaction"""
    if not st.session_state.wallet_credentials:
        return None
    
    session = get_authenticated_session()
    if not session:
        return None
    
    # Create unique object ID using transaction ID and user email
    user_email = st.session_state.user_profile.get('email', 'user')
    object_suffix = f"{re.sub(r'[^w.-]', '_', user_email)}_{transaction['id']}"
    object_id = f'{ISSUER_ID}.{object_suffix}'
    
    # Define the receipt pass object
    receipt_object = {
        'id': object_id,
        'classId': CLASS_ID,
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
                'value': 'Cash Snap AI Receipt'
            }
        },
        'subheader': {
            'defaultValue': {
                'language': 'en',
                'value': f"Transaction #{transaction['id']}"
            }
        },
        'header': {
            'defaultValue': {
                'language': 'en',
                'value': transaction.get('merchant', 'Unknown Merchant')
            }
        },
        'barcode': {
            'type': 'QR_CODE',
            'value': f"transaction_{transaction['id']}"
        },
        'heroImage': {
            'sourceUri': {
                'uri': 'https://storage.googleapis.com/wallet-lab-tools-codelab-artifacts-public/google-io-hero-demo-only.jpg'
            }
        },
        'textModulesData': [
            {
                'header': 'TOTAL',
                'body': f"${transaction.get('total', 0):.2f}",
                'id': 'total_amount'
            },
            {
                'header': 'CATEGORY',
                'body': transaction.get('category', 'Other').title(),
                'id': 'category'
            },
            {
                'header': 'MERCHANT',
                'body': transaction.get('merchant', 'Unknown'),
                'id': 'merchant'
            },
            {
                'header': 'DATE',
                'body': transaction.get('date', ''),
                'id': 'transaction_date'
            },
            {
                'header': 'PAYMENT',
                'body': transaction.get('payment_method', 'Unknown').title(),
                'id': 'payment_method'
            }
        ]
    }
    
    try:
        # Check if the object already exists
        response = session.get(f'{BASE_URL}/genericObject/{object_id}')
        
        if response.status_code != 200:
            # Object does not exist, create it
            response = session.post(
                f'{BASE_URL}/genericObject',
                json=receipt_object
            )
            
            if response.status_code not in [200, 201]:
                st.error(f'Error creating wallet object: {response.status_code} - {response.text}')
                return None
        
        # Create the signed JWT for the "Add to Google Wallet" button
        credentials_info = st.session_state.wallet_credentials['credentials_info']
        claims = {
            'iss': credentials_info['client_email'],
            'aud': 'google',
            'origins': ['https://localhost:8501', 'http://localhost:8501'],  # Streamlit default
            'typ': 'savetowallet',
            'payload': {
                'genericObjects': [receipt_object]
            }
        }
        
        # Sign the JWT using the service account private key
        token = jwt.encode(claims, credentials_info['private_key'], algorithm='RS256')
        
        # Handle string/bytes difference in different PyJWT versions
        if isinstance(token, bytes):
            token = token.decode('utf-8')
            
        save_url = f'https://pay.google.com/gp/v/save/{token}'
        
        return save_url
        
    except Exception as error:
        st.error(f'Error creating wallet pass: {error}')
        return None

# Utility functions (keeping original ones)
def make_json_serializable(obj):
    """Convert non-serializable objects to JSON-serializable format"""
    if isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(item) for item in obj]
    elif isinstance(obj, (datetime, pd.Timestamp)):
        return obj.isoformat()
    elif isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj
    else:
        return str(obj)

def validate_transaction_data(result):
    """Validate and sanitize transaction data"""
    required_fields = ['date', 'merchant', 'items', 'subtotal', 'tax', 'total', 'category', 'payment_method']
    for field in required_fields:
        if field not in result:
            result[field] = None
    
    # Ensure numerical fields are numbers
    for field in ['subtotal', 'tax', 'total']:
        if result[field] is not None:
            try:
                result[field] = float(result[field])
            except (ValueError, TypeError):
                result[field] = 0.0
    
    # Validate items
    if not isinstance(result.get('items'), list):
        result['items'] = []
    for item in result['items']:
        for field in ['quantity', 'unit_price', 'total_price']:
            if field in item and item[field] is not None:
                try:
                    item[field] = float(item[field])
                except (ValueError, TypeError):
                    item[field] = 0.0
    
    # Validate category and payment_method
    valid_categories = ["groceries", "restaurant", "shopping", "utilities", "transport", 
                        "entertainment", "healthcare", "other"]
    valid_payment_methods = ["cash", "card", "digital"]
    result['category'] = result.get('category', 'other') if result.get('category') in valid_categories else 'other'
    result['payment_method'] = result.get('payment_method', 'cash') if result.get('payment_method') in valid_payment_methods else 'cash'
    
    return result

# Mock database functions (keeping original ones)
def save_transactions():
    """Save transactions to JSON file"""
    try:
        serializable_transactions = make_json_serializable(st.session_state.transactions)
        with open(JSON_FILE_PATH, 'w') as f:
            json.dump(serializable_transactions, f, indent=2)
        return True
    except Exception as e:
        st.error(f"Failed to save transactions: {str(e)}")
        return False

def load_transactions():
    """Load transactions from JSON file"""
    try:
        with open(JSON_FILE_PATH, 'r') as f:
            st.session_state.transactions = json.load(f)
    except FileNotFoundError:
        st.session_state.transactions = []

def save_user_profile():
    """Save user profile to JSON file"""
    try:
        with open(USER_PROFILE_PATH, 'w') as f:
            json.dump(st.session_state.user_profile, f, indent=2)
        return True
    except Exception as e:
        st.error(f"Failed to save user profile: {str(e)}")
        return False

def load_user_profile():
    """Load user profile from JSON file"""
    try:
        with open(USER_PROFILE_PATH, 'r') as f:
            st.session_state.user_profile = json.load(f)
    except FileNotFoundError:
        st.session_state.user_profile = {}

# Initialize Gemini AI (keeping original functions)
def init_gemini():
    """Initialize Gemini AI"""
    api_key = st.sidebar.text_input("Enter Gemini API Key", type="password")
    if api_key:
        genai.configure(api_key=api_key)
        return True
    return False

def analyze_receipt_with_gemini(image_data=None, text_data=None):
    """Analyze receipt using Gemini"""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = """
        Analyze this receipt and extract the following information in JSON format:
        {
            "date": "YYYY-MM-DD",
            "merchant": "store name",
            "items": [
                {
                    "name": "item name",
                    "quantity": number,
                    "unit_price": number,
                    "total_price": number
                }
            ],
            "subtotal": number,
            "tax": number,
            "total": number,
            "category": "groceries/restaurant/shopping/utilities/transport/entertainment/healthcare/other",
            "payment_method": "cash/card/digital"
        }
        
        If any information is not clearly visible, use reasonable defaults or null values.
        Ensure all prices are in numerical format without currency symbols.
        """
        
        if image_data:
            response = model.generate_content([prompt, image_data])
        else:
            response = model.generate_content(f"{prompt}\n\nReceipt text: {text_data}")
        
        response_text = response.text
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            return None
    except Exception as e:
        st.error(f"Error analyzing receipt: {str(e)}")
        return None

def get_financial_advice(query, transactions, user_profile):
    """Get financial advice using Gemini"""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        total_spent = sum(t.get('total', 0) for t in transactions)
        categories = {}
        for t in transactions:
            cat = t.get('category', 'other')
            categories[cat] = categories.get(cat, 0) + t.get('total', 0)
        
        context = f"""
        User Profile: {user_profile}
        Total Transactions: {len(transactions)}
        Total Spent: {total_spent:.2f} inr
        Spending by Category: {categories}
        Recent Transactions: {transactions[-5:] if transactions else []}
        
        User Query: {query}
        
        Provide helpful financial advice based on this data. Be specific and actionable.
        If the user asks about spending patterns, provide insights.
        If they ask about saving money, give practical suggestions.
        Keep the response conversational and helpful.
        """
        
        response = model.generate_content(context)
        return response.text
    except Exception as e:
        return f"Sorry, I couldn't process your request: {str(e)}"

# Authentication and Profile Setup (keeping original)
def show_login_page():
    st.title("🏦 Welcome to Cash Snap AI")
    st.subheader("Your Personal Financial Assistant with Google Wallet Integration")
    
    with st.form("login_form"):
        st.write("### Quick Setup")
        name = st.text_input("Your Name")
        email = st.text_input("Email")
        monthly_income = st.number_input("Monthly Income ($)", min_value=0, value=5000)
        
        st.write("### Tell us about yourself")
        financial_goals = st.selectbox(
            "Primary Financial Goal",
            ["Save for emergency fund", "Pay off debt", "Save for major purchase", 
             "Retirement planning", "General budgeting"]
        )
        
        spending_personality = st.selectbox(
            "Spending Personality",
            ["Conservative spender", "Moderate spender", "Impulsive spender", "Varies by situation"]
        )
        
        stress_level = st.slider("Financial Stress Level (1-10)", 1, 10, 5)
        
        submitted = st.form_submit_button("Get Started")
        
        if submitted and name and email:
            st.session_state.user_profile = {
                "name": name,
                "email": email,
                "monthly_income": monthly_income,
                "financial_goals": financial_goals,
                "spending_personality": spending_personality,
                "stress_level": stress_level,
                "created_at": datetime.now().isoformat()
            }
            st.session_state.authenticated = True
            if save_user_profile():
                st.success("Profile created successfully!")
                st.rerun()
            else:
                st.error("Failed to save profile.")

# Main Application
def show_main_app():
    load_transactions()
    load_user_profile()
    
    st.sidebar.title("💰 Cash Snap AI")
    st.sidebar.write(f"Welcome, {st.session_state.user_profile.get('name', 'User')}!")
    
    # Google Wallet Setup
    wallet_enabled = setup_google_wallet()
    
    if not init_gemini():
        st.sidebar.warning("Please enter your Gemini API key to use AI features")
        gemini_available = False
    else:
        gemini_available = True
    
    page = st.sidebar.selectbox(
        "Navigate",
        ["📸 Add Transaction", "📊 Dashboard", "💬 Chat with AI", "👤 Profile", "📋 Transaction History"]
    )
    
    if page == "📸 Add Transaction":
        show_add_transaction_page(gemini_available, wallet_enabled)
    elif page == "📊 Dashboard":
        show_dashboard_page()
    elif page == "💬 Chat with AI":
        show_chat_page(gemini_available)
    elif page == "👤 Profile":
        show_profile_page()
    elif page == "📋 Transaction History":
        show_transaction_history_page()

def show_add_transaction_page(gemini_available, wallet_enabled):
    st.title("📸 Add New Transaction")
    
    if wallet_enabled:
        st.info("🏦 Google Wallet integration is enabled! You'll get a digital receipt after adding transactions.")
    
    tab1, tab2 = st.tabs(["📱 Upload Receipt", "✍️ Manual Entry"])
    
    with tab1:
        st.subheader("Upload Receipt Image/Video/PDF")
    
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=['png', 'jpg', 'jpeg', 'pdf', 'mp4', 'mov'],
            help="Upload receipt image, PDF, or video"
        )
    
        if uploaded_file and gemini_available:
            if uploaded_file.type.startswith('image'):
                image = Image.open(uploaded_file)
                st.image(image, caption="Uploaded Receipt", width=400)
                
                if st.button("🤖 Analyze with AI"):
                    with st.spinner("Analyzing receipt..."):
                        result = analyze_receipt_with_gemini(image_data=image)
                        if result:
                            st.success("Receipt analyzed successfully!")
                            result = validate_transaction_data(result)
                            st.json(result)
                            
                            result['id'] = len(st.session_state.transactions) + 1
                            result['created_at'] = datetime.now().isoformat()
                            result['source'] = 'image_upload'
                            st.session_state.transactions.append(result)
                            
                            if save_transactions():
                                st.success("Transaction saved successfully!")
                                
                                # Google Wallet Integration
                                if wallet_enabled:
                                    st.info("🔄 Creating Google Wallet pass...")
                                    
                                    # Ensure class exists
                                    if create_receipt_pass_class():
                                        wallet_url = create_receipt_wallet_pass(result)
                                        
                                        if wallet_url:
                                            st.success("✅ Google Wallet pass created!")
                                            st.markdown(f"""
                                            ### 🏦 Add to Google Wallet
                                            Click the button below to add your receipt to Google Wallet:
                                            
                                            <a href="{wallet_url}" target="_blank">
                                                <img src="https://developers.google.com/wallet/images/add-to-google-wallet/wallet-button.png" 
                                                     alt="Add to Google Wallet" style="height: 50px;">
                                            </a>
                                            """, unsafe_allow_html=True)
                                        else:
                                            st.warning("Failed to create Google Wallet pass")
                                    else:
                                        st.warning("Failed to setup Google Wallet class")
                                        
                            else:
                                st.error("Failed to save transaction. Check file permissions or data format.")
            else:
                st.info("PDF/Video analysis will be available in the full version")
    
    with tab2:
        st.subheader("Manual Transaction Entry")
        
        with st.form("manual_transaction"):
            col1, col2 = st.columns(2)
            
            with col1:
                date = st.date_input("Date", datetime.now())
                merchant = st.text_input("Merchant/Store")
                category = st.selectbox(
                    "Category",
                    ["groceries", "restaurant", "shopping", "utilities", "transport", 
                     "entertainment", "healthcare", "other"]
                )
                payment_method = st.selectbox("Payment Method", ["cash", "card", "digital"])
            
            with col2:
                total = st.number_input("Total Amount ($)", min_value=0.0, format="%.2f")
                tax = st.number_input("Tax ($)", min_value=0.0, format="%.2f")
                notes = st.text_area("Notes (optional)")
            
            submitted = st.form_submit_button("Add Transaction")
            
            if submitted and merchant and total > 0:
                transaction = {
                    'id': len(st.session_state.transactions) + 1,
                    'date': date.isoformat(),
                    'merchant': merchant,
                    'category': category,
                    'total': total,
                    'tax': tax,
                    'payment_method': payment_method,
                    'notes': notes,
                    'source': 'manual_entry',
                    'created_at': datetime.now().isoformat()
                }
                st.session_state.transactions.append(transaction)
                
                if save_transactions():
                    st.success("Transaction added successfully!")
                    
                    # Google Wallet Integration
                    if wallet_enabled:
                        st.info("🔄 Creating Google Wallet pass...")
                        
                        # Ensure class exists
                        if create_receipt_pass_class():
                            wallet_url = create_receipt_wallet_pass(transaction)
                            
                            if wallet_url:
                                st.success("✅ Google Wallet pass created!")
                                st.markdown(f"""
                                ### 🏦 Add to Google Wallet
                                Click the button below to add your receipt to Google Wallet:
                                
                                <a href="{wallet_url}" target="_blank">
                                    <img src="https://developers.google.com/wallet/images/add-to-google-wallet/wallet-button.png" 
                                         alt="Add to Google Wallet" style="height: 50px;">
                                </a>
                                """, unsafe_allow_html=True)
                            else:
                                st.warning("Failed to create Google Wallet pass")
                        else:
                            st.warning("Failed to setup Google Wallet class")
                else:
                    st.error("Failed to save transaction.")

# Keep all other original functions unchanged
def show_dashboard_page():
    st.title("📊 Financial Dashboard")
    
    if not st.session_state.transactions:
        st.info("No transactions yet. Add some transactions to see your dashboard!")
        return
    
    df = pd.DataFrame(st.session_state.transactions)
    df['date'] = pd.to_datetime(df['date'])
    df['total'] = pd.to_numeric(df['total'], errors='coerce')
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_transactions = len(df)
        st.metric("Total Transactions", total_transactions)
    
    with col2:
        total_spent = df['total'].sum()
        st.metric("Total Spent", f"${total_spent:,.2f}")
    
    with col3:
        avg_transaction = df['total'].mean()
        st.metric("Avg Transaction", f"${avg_transaction:.2f}")
    
    with col4:
        monthly_income = st.session_state.user_profile.get('monthly_income', 0)
        if monthly_income > 0:
            spending_rate = (total_spent / monthly_income) * 100
            st.metric("Spending Rate", f"{spending_rate:.1f}%")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Spending by Category")
        category_spending = df.groupby('category')['total'].sum().reset_index()
        fig_pie = px.pie(category_spending, values='total', names='category', 
                        title="Spending Distribution")
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        st.subheader("Spending Over Time")
        daily_spending = df.groupby(df['date'].dt.date)['total'].sum().reset_index()
        fig_line = px.line(daily_spending, x='date', y='total', 
                          title="Daily Spending Trend")
        st.plotly_chart(fig_line, use_container_width=True)
    
    st.subheader("Recent Transactions")
    recent_df = df.sort_values('created_at', ascending=False).head(10)
    st.dataframe(recent_df[['date', 'merchant', 'category', 'total', 'payment_method']], 
                use_container_width=True)

def show_chat_page(gemini_available):
    st.title("💬 Chat with Cash Snap AI")
    
    if not gemini_available:
        st.warning("Please enter your Gemini API key in the sidebar to use the AI chat feature.")
        return
    
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    
    for message in st.session_state.chat_history:
        if message['role'] == 'user':
            st.chat_message("user").write(message['content'])
        else:
            st.chat_message("assistant").write(message['content'])
    
    user_input = st.chat_input("Ask me about your finances...")
    
    if user_input:
        st.session_state.chat_history.append({'role': 'user', 'content': user_input})
        st.chat_message("user").write(user_input)
        
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = get_financial_advice(
                    user_input, 
                    st.session_state.transactions, 
                    st.session_state.user_profile
                )
                st.write(response)
                st.session_state.chat_history.append({'role': 'assistant', 'content': response})
    
    st.subheader("💡 Try asking:")
    suggestions = [
        "How much did I spend on groceries this month?",
        "What are my biggest spending categories?",
        "How can I save money on my current spending?",
        "Am I spending too much compared to my income?",
        "What's my spending trend over time?"
    ]
    
    for suggestion in suggestions:
        if st.button(suggestion, key=f"suggest_{suggestion}"):
            st.session_state.chat_history.append({'role': 'user', 'content': suggestion})
            response = get_financial_advice(
                suggestion, 
                st.session_state.transactions, 
                st.session_state.user_profile
            )
            st.session_state.chat_history.append({'role': 'assistant', 'content': response})
            st.rerun()

def show_profile_page():
    st.title("👤 User Profile")
    
    profile = st.session_state.user_profile
    
    with st.form("profile_form"):
        st.subheader("Personal Information")
        name = st.text_input("Name", value=profile.get('name', ''))
        email = st.text_input("Email", value=profile.get('email', ''))
        monthly_income = st.number_input("Monthly Income ($)", 
                                       value=profile.get('monthly_income', 0))
        
        st.subheader("Financial Preferences")
        financial_goals = st.selectbox(
            "Primary Financial Goal",
            ["Save for emergency fund", "Pay off debt", "Save for major purchase", 
             "Retirement planning", "General budgeting"],
            index=0 if not profile.get('financial_goals') else 
            ["Save for emergency fund", "Pay off debt", "Save for major purchase", 
             "Retirement planning", "General budgeting"].index(profile.get('financial_goals', ''))
        )
        
        spending_personality = st.selectbox(
            "Spending Personality",
            ["Conservative spender", "Moderate spender", "Impulsive spender", "Varies by situation"],
            index=0 if not profile.get('spending_personality') else
            ["Conservative spender", "Moderate spender", "Impulsive spender", "Varies by situation"].index(profile.get('spending_personality', ''))
        )
        
        stress_level = st.slider("Financial Stress Level (1-10)", 1, 10, 
                               profile.get('stress_level', 5))
        
        if st.form_submit_button("Update Profile"):
            st.session_state.user_profile.update({
                "name": name,
                "email": email,
                "monthly_income": monthly_income,
                "financial_goals": financial_goals,
                "spending_personality": spending_personality,
                "stress_level": stress_level,
                "updated_at": datetime.now().isoformat()
            })
            if save_user_profile():
                st.success("Profile updated successfully!")
            else:
                st.error("Failed to update profile.")

def show_transaction_history_page():
    st.title("📋 Transaction History")
    
    if not st.session_state.transactions:
        st.info("No transactions yet. Add some transactions to see your history!")
        return
    
    df = pd.DataFrame(st.session_state.transactions)
    df['date'] = pd.to_datetime(df['date'])
    df['total'] = pd.to_numeric(df['total'], errors='coerce')
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        date_range = st.date_input(
            "Date Range",
            value=(df['date'].min().date(), df['date'].max().date()),
            format="YYYY-MM-DD"
        )
    
    with col2:
        categories = st.multiselect(
            "Categories",
            options=df['category'].unique(),
            default=df['category'].unique()
        )
    
    with col3:
        min_amount = st.number_input("Min Amount", value=0.0)
    
    filtered_df = df[
        (df['date'].dt.date >= date_range[0]) &
        (df['date'].dt.date <= date_range[1]) &
        (df['category'].isin(categories)) &
        (df['total'] >= min_amount)
    ]
    
    st.subheader(f"Showing {len(filtered_df)} transactions")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Amount", f"${filtered_df['total'].sum():.2f}")
    with col2:
        st.metric("Average", f"${filtered_df['total'].mean():.2f}")
    with col3:
        st.metric("Count", len(filtered_df))
    
    # Add Google Wallet Pass Generation for existing transactions
    if st.session_state.wallet_credentials:
        st.subheader("🏦 Generate Google Wallet Passes")
        
        if st.button("Generate Passes for Selected Transactions"):
            if create_receipt_pass_class():
                wallet_urls = []
                
                progress_bar = st.progress(0)
                for i, (_, transaction) in enumerate(filtered_df.iterrows()):
                    transaction_dict = transaction.to_dict()
                    wallet_url = create_receipt_wallet_pass(transaction_dict)
                    if wallet_url:
                        wallet_urls.append((transaction_dict['id'], wallet_url))
                    progress_bar.progress((i + 1) / len(filtered_df))
                
                if wallet_urls:
                    st.success(f"✅ Generated {len(wallet_urls)} Google Wallet passes!")
                    
                    st.subheader("📱 Add to Google Wallet")
                    for trans_id, url in wallet_urls[:5]:  # Show first 5
                        st.markdown(f"""
                        **Transaction #{trans_id}**: 
                        <a href="{url}" target="_blank">
                            <img src="https://developers.google.com/wallet/images/add-to-google-wallet/wallet-button.png" 
                                 alt="Add to Google Wallet" style="height: 40px;">
                        </a>
                        """, unsafe_allow_html=True)
                    
                    if len(wallet_urls) > 5:
                        st.info(f"... and {len(wallet_urls) - 5} more passes generated")
                else:
                    st.warning("Failed to generate any Google Wallet passes")
            else:
                st.error("Failed to setup Google Wallet class")
    
    display_df = filtered_df.sort_values('date', ascending=False)
    st.dataframe(
        display_df[['date', 'merchant', 'category', 'total', 'payment_method', 'source']],
        use_container_width=True
    )
    
    csv = display_df.to_csv(index=False)
    st.download_button(
        label="📥 Download CSV",
        data=csv,
        file_name=f"transactions_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

def main():
    if not st.session_state.authenticated and not st.session_state.user_profile:
        show_login_page()
    else:
        st.session_state.authenticated = True
        show_main_app()

if __name__ == "__main__":
    main()