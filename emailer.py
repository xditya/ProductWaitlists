import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config import Config


def send_html_email(
    receiver_email, waitlist_current_position, waitlist_total_size, referral_code
):
    """Sends an email with HTML content from a file.

    Args:
        receiver_email (str): The email address of the recipient.
    """
    try:
        # Create a multipart message
        message = MIMEMultipart()
        message["From"] = Config.EMAIL_SENDER
        message["To"] = receiver_email
        message["Subject"] = "[ArcConsoles] Thanks for joining the waitlist!"

        # Open and read the HTML file
        with open("./mail_content.html", "r") as f:
            html_body = f.read()

        # Replace placeholders in the HTML content
        html_body = (
            html_body.replace(
                "{{waitlist_current_position}}", str(waitlist_current_position)
            )
            .replace("{{waitlist_total_size}}", str(waitlist_total_size))
            .replace("{{email}}", receiver_email)
        )

        if referral_code:
            html_body = html_body.replace("{{referral_code}}", referral_code)

        # Attach the HTML content to the message
        message.attach(MIMEText(html_body, "html"))

        # Connect to the SMTP server
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            # Log in to the email account
            server.login(Config.EMAIL_SENDER, Config.EMAIL_PASSWORD)

            # Send the email
            server.sendmail(Config.EMAIL_SENDER, receiver_email, message.as_string())

        logging.info("HTML email sent successfully!")

    except FileNotFoundError:
        logging.error(f"Error: HTML file not found!")
    except Exception as e:
        logging.exception(f"Error sending email: {e}")
