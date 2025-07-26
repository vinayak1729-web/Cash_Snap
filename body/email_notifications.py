import streamlit as st
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import pandas as pd
from app import get_currency_symbol
# Load environment variables
load_dotenv()

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send email using SMTP"""
    try:
        # Set up the MIME
        message = MIMEMultipart()
        message["From"] = EMAIL_SENDER
        message["To"] = to_email
        message["Subject"] = subject

        # Add body to email
        message.attach(MIMEText(body, "plain"))

        # Create SMTP session
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(message)
        return True
    except Exception as e:
        st.error(f"Failed to send email: {str(e)}")
        return False

def check_and_trigger_emails():
    """Check conditions and trigger email notifications"""
    if not st.session_state.authenticated or not st.session_state.user_profile:
        return

    user_email = st.session_state.user_profile.get('email', '')
    monthly_income = st.session_state.user_profile.get('monthly_income', 0)
    currency_symbol = get_currency_symbol()

    if not user_email or not monthly_income:
        return

    # Condition 1: Check if spending exceeds 80% of monthly income
    if st.session_state.transactions:
        df = pd.DataFrame(st.session_state.transactions)
        df['total'] = pd.to_numeric(df['total'], errors='coerce')
        total_spent = df['total'].sum()
        spending_ratio = total_spent / monthly_income if monthly_income > 0 else 0

        if spending_ratio > 0.8:
            subject = "⚠️ Cash Snap AI: High Spending Alert"
            body = f"""
Dear {st.session_state.user_profile.get('name', 'User')},

You've spent {spending_ratio:.0%} of your monthly income ({currency_symbol}{monthly_income:,.2f})!
Current total spending: {currency_symbol}{total_spent:,.2f}

Here are some quick tips to manage your expenses:
1. Review your recent transactions in the Cash Snap AI dashboard
2. Consider creating a budget for discretionary spending
3. Try our AI chat feature for personalized saving suggestions

Visit your dashboard to get a detailed spending optimization plan!

Best regards,
Cash Snap AI Team
"""
            send_email(user_email, subject, body)

    # Condition 2: Check for prepaid receipts and send reminders
    current_time = datetime.now()
    
    for transaction in st.session_state.transactions:
        if transaction.get('category') == 'prepaid' and transaction.get('date'):
            try:
                trans_date = datetime.fromisoformat(transaction['date'].replace('Z', '+00:00'))
                
                # Calculate times for reminders
                one_day_prior = trans_date - timedelta(days=1)
                one_hour_prior = trans_date - timedelta(hours=1)

                # Check if current time is within 10 minutes of reminder times
                time_diff_day = abs((current_time - one_day_prior).total_seconds() / 60)
                time_diff_hour = abs((current_time - one_hour_prior).total_seconds() / 60)

                if time_diff_day <= 10:  # Within 10 minutes of 1 day prior
                    subject = f"🔔 Cash Snap AI: Prepaid Receipt Reminder (1 Day)"
                    body = f"""
Dear {st.session_state.user_profile.get('name', 'User')},

This is a reminder for your prepaid transaction:
- Merchant: {transaction.get('merchant', 'Unknown')}
- Amount: {currency_symbol}{transaction.get('total', 0):.2f}
- Date: {trans_date.strftime('%Y-%m-%d')}
- Category: {transaction.get('category', 'prepaid').title()}

The event is scheduled for tomorrow. Please review the details in your Cash Snap AI dashboard.

Best regards,
Cash Snap AI Team
"""
                    send_email(user_email, subject, body)

                if time_diff_hour <= 10:  # Within 10 minutes of 1 hour prior
                    subject = f"🔔 Cash Snap AI: Prepaid Receipt Reminder (1 Hour)"
                    body = f"""
Dear {st.session_state.user_profile.get('name', 'User')},

This is your final reminder for your prepaid transaction:
- Merchant: {transaction.get('merchant', 'Unknown')}
- Amount: {currency_symbol}{transaction.get('total', 0):.2f}
- Date: {trans_date.strftime('%Y-%m-%d %H:%M')}
- Category: {transaction.get('category', 'prepaid').title()}

The event is happening in approximately one hour. Check your Cash Snap AI dashboard for more details.

Best regards,
Cash Snap AI Team
"""
                    send_email(user_email, subject, body)

            except ValueError as e:
                st.error(f"Error parsing date for transaction {transaction.get('id', 'N/A')}: {str(e)}")