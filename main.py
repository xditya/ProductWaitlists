from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import logging
import time

from database import (
    add_to_waitlist,
    get_email_by_referral_code,
    get_referral_code_from_email,
    get_waitlist_positions,
    get_users,
    get_user_position,
    get_waitlist_size,
    get_referral_count,
    is_referral_code_existing,
    remove_from_waitlist,
    get_referred_by,
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
    data = request.get_json()
    if not data or "email" not in data:
        return jsonify({"error": "Invalid request"}), 400

    email = data["email"]
    phone = data.get("phone", 0)
    referral_code = data.get("referral_code")

    if referral_code:
        if not is_referral_code_existing(referral_code):
            return jsonify({"error": "Invalid referral code"}), 400

        referrer_email = get_email_by_referral_code(referral_code)
        if email == referrer_email:
            return jsonify({"error": "You cannot refer yourself"}), 400

    try:
        if not add_to_waitlist(email, phone, referral_code):
            return jsonify({"error": "Already in waitlist"}), 400

        # Get user's position and total waitlist size
        position = get_user_position(email)
        total_size = get_waitlist_size()
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
                "error": None,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/waitlist", methods=["GET"])
def get_waitlist_ep():
    try:
        positions = get_waitlist_positions()
        users = get_users()

        # Combine user info with positions
        waitlist = []
        for email, position in positions.items():
            user_info = users.get(email, {})
            waitlist.append(
                {
                    "email": email,
                    "position": position,
                    "phone": user_info.get("phone", 0),
                    "referral_code": user_info.get("referral_code", ""),
                    "referral_count": user_info.get("referrals", 0),
                    "referred_by": user_info.get("referred_by_email", None),
                }
            )

        # Sort by position
        waitlist.sort(key=lambda x: x["position"])

        return jsonify(
            {"waitlist": waitlist, "total_size": len(waitlist), "error": None}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/position/<email>", methods=["GET"])
def get_position_ep(email):
    try:
        position = get_user_position(email)
        if position is None:
            return jsonify({"error": "User not found in waitlist"}), 404

        total_size = get_waitlist_size()
        referral_count = get_referral_count(email)
        referred_by = get_referred_by(email)

        return jsonify(
            {
                "position": position,
                "total_size": total_size,
                "referral_count": referral_count,
                "referred_by": referred_by,
                "error": None,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/check", methods=["GET"])
def check_waitlist_ep():
    data = request.args
    if not data or "email" not in data:
        return send_from_directory("static", "404.html")
    referral_code = get_referral_code_from_email(data["email"])
    current_position = get_user_position(data["email"])
    total_size = get_waitlist_size()
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


@app.route("/referrals/<email>", methods=["GET"])
def get_referrals_ep(email):
    try:
        referral_count = get_referral_count(email)
        return jsonify({"referral_count": referral_count, "error": None})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Admin endpoints
@app.route("/admin")
def admin_dashboard():
    return send_from_directory("static", "dashboard.html")


@app.route("/admin/waitlist", methods=["GET"])
def admin_waitlist_ep():
    try:
        positions = get_waitlist_positions()
        users = get_users()

        # Combine user info with positions
        waitlist = []
        for email, position in positions.items():
            user_info = users.get(email, {})
            waitlist.append(
                {
                    "email": email,
                    "position": position,
                    "phone": user_info.get("phone", 0),
                    "referral_code": user_info.get("referral_code", ""),
                    "referral_count": user_info.get("referrals", 0),
                    "referred_by": user_info.get("referred_by_email", None),
                }
            )

        # Sort by position
        waitlist.sort(key=lambda x: x["position"])

        return jsonify(
            {"waitlist": waitlist, "total_size": len(waitlist), "error": None}
        )
    except Exception as e:
        import traceback

        print(f"Error in admin_waitlist_ep: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500


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
