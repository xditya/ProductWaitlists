from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import logging
import time

from database import (
    add_to_waitlist,
    get_all_referral_codes,
    get_email_by_referral_code,
    get_full_waitlist,
    get_referral_code_from_email,
    get_referral_count,
    get_waitlist_position,
    is_referral_code_existing,
    remove_from_waitlist,
)
from emailer import send_html_email

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask("waitlists")
CORS(app)


@app.route("/")
def hello():
    return jsonify({"message": "Hello, World!", "error": None})


@app.route("/joinwaitlist", methods=["POST"])
def join_waitlist_ep():
    """Join Waitlist Endpoint
    This endpoint allows users to join the waitlist by providing their email and optional phone number and referral code.

    Parameters:
    - email (str): The email address of the user.
    - phone (str, optional): The phone number of the user. Defaults to 0.
    - referral_code (str, optional): The code of the user who referred them.
    """

    data = request.get_json()
    if not data or "email" not in data:
        return jsonify({"error": "Invalid request"}), 400

    email = data["email"]
    phone = data.get("phone", 0)
    referred_by = data.get("referral_code")
    referrer_email = None

    if referred_by:
        if not is_referral_code_existing(referred_by):
            return jsonify({"error": "Invalid referral code"}), 400

        referrer_email = get_email_by_referral_code(referred_by)
        if email == referrer_email:
            return jsonify({"error": "You cannot refer yourself"}), 400

    try:
        if not add_to_waitlist(email, phone, referrer_email):
            return jsonify({"error": "Already in waitlist"}), 400

        # Get user's position and total waitlist size
        position = get_waitlist_position(email)
        total_size = len(get_full_waitlist())
        referral_count = get_referral_count(email)
        user_ref_code = get_referral_code_from_email(email)
        send_html_email(
            email,
            position,
            total_size,
            user_ref_code,
        )
        return jsonify(
            {
                "message": "Added to waitlist",
                "position": position,
                "total_size": total_size,
                "referral_count": referral_count,
                "referral_code": user_ref_code,
                "error": None,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/check", methods=["GET"])
def check_waitlist_ep():
    """
    This endpoint returns the users position in the waitlist as an HTML page.
    To be referenced in the email sent to the user after joining the waitlist.
    """
    data = request.args
    if not data or "email" not in data:
        return send_from_directory("static", "404.html")
    referral_code = get_referral_code_from_email(data["email"])
    current_position = get_waitlist_position(data["email"])
    total_size = len(get_full_waitlist())
    time1 = time.strftime("%d/%m/%y %H:%M:%S")

    if not current_position and not referral_code:
        logging.info(
            f"User {data['email']} not found in waitlist and no referral code."
        )
        return send_from_directory("static", "404.html")

    html_content = ""
    with open("./static/waitlist.html", "r") as f:
        html_content = f.read()
    html_content = (
        html_content.replace("{{waitlist_position}}", str(current_position))
        .replace("{{total_waitlist}}", str(total_size))
        .replace("{{referral_code}}", referral_code)
        .replace("{{time}}", time1)
    )
    return html_content


# Admin endpoints
@app.route("/admin")
def admin_dashboard():
    return send_from_directory("static", "admin_dashboard.html")


@app.route("/admin/waitlist", methods=["GET"])
def get_waitlist_ep():
    """
    Testing endpoint to get the waitlist size and positions.
    """

    waitlist_full = get_full_waitlist()
    if not waitlist_full:
        return jsonify({"error": "No users in waitlist"}), 404

    return jsonify(waitlist_full)


@app.route("/admin/referrals", methods=["GET"])
def get_referrals_ep():
    refs = get_all_referral_codes()
    if not refs:
        return jsonify({"error": "No users in waitlist"}), 404
    return jsonify({"error": None, "referrals": refs})


@app.route("/admin/remove/<email>", methods=["DELETE"])
def admin_remove_ep(email):
    try:
        if remove_from_waitlist(email):
            return jsonify({"message": "User removed successfully", "error": None})
        return jsonify({"error": "User not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(port=5000, debug=True)
