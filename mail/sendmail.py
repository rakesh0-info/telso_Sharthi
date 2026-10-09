import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv



load_dotenv()

# Read the configurations safely
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com").strip() # Fallback to default if missing
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))             # Convert port to integer
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SMTP_PASSWORD") 


def send_mail(receiver_mail: str, otp: str):
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = receiver_mail
    msg["Subject"] = "Your Verification OTP"
    
    body_content = f"This is your OTP: {otp}. It will expire in 5 minutes."
    msg.attach(MIMEText(body_content, "plain"))

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print("Error sending mail: ", e)


