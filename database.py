import datetime
import string
import random
import redis
import logging

from config import Config
from helpers import dump_json, load_json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Redis connection
db = redis.Redis(
    host=Config.REDIS_HOST,
    port=Config.REDIS_PORT,
    password=Config.REDIS_PASSWORD,
    username=Config.REDIS_USERNAME,
    decode_responses=True,
)

REFERRALS_STORE = "REFERRALS"
WAITLIST_STORE = "WAITLISTS"


def generate_referral_code():
    code = None
    while code is None or is_referral_code_existing(code):
        characters = string.ascii_uppercase + string.digits
        code = "".join(random.choice(characters) for _ in range(5))
    return "ARC" + code


def add_referral_code(code, email):
    refs = load_json(db.get(REFERRALS_STORE))
    if code not in refs:
        refs[code] = email
        db.set(REFERRALS_STORE, dump_json(refs))
        logger.info(f"Added referral code {code} for email {email}")
        return True
    return False


def is_referral_code_existing(code):
    refs = load_json(db.get(REFERRALS_STORE))
    if code in refs:
        return True
    return False


def get_all_referral_codes():
    """Returns all referral codes."""
    refs = load_json(db.get(REFERRALS_STORE))
    return refs


def add_to_waitlist(email, phone, referred_by):
    """Adds the user email to waitlist, increments referrer count, and recalculates positions."""
    waitlist = load_json(db.get(WAITLIST_STORE))
    if not waitlist:
        waitlist = {}

    if email in waitlist:
        logger.info(f"Email {email} already in waitlist")
        # Optionally, return the existing user's position
        return waitlist[email]["position"]  # Return existing position

    user_referral_code = generate_referral_code()
    # Assuming add_referral_code maps the code to the email somewhere else if needed
    add_referral_code(user_referral_code, email)

    # Add the new user to the dictionary
    # The initial position is not important here, it will be set by recalculate_positions
    waitlist[email] = {
        "phone": phone,
        "referred_by": referred_by,
        "joined_at": str(datetime.datetime.now()),  # Store time for tie-breaking
        "referrals": 0,
        "referral_code": user_referral_code,
        "position": None,  # Position will be set after sorting
        "email": email,  # Add email to user data for easy sorting/mapping
    }

    # Increment referrer's count if applicable
    if referred_by:
        if referred_by in waitlist:
            waitlist[referred_by]["referrals"] += 1
            logger.info(
                f"Incremented referral count of {referred_by} to {waitlist[referred_by]['referrals']}"
            )
        else:
            logger.warning(
                f"Referrer {referred_by} not found in waitlist. Referral not counted."
            )
            # You might want to handle this case - maybe the code was invalid or referrer deleted?

    # After potentially adding a user and incrementing a referral count,
    # recalculate positions for everyone.
    recalculate_positions(waitlist)

    # Save the updated waitlist
    db.set(WAITLIST_STORE, dump_json(waitlist))

    logger.info(f"Added {email} to waitlist and recalculated positions.")

    # Return the new user's calculated position
    return waitlist[email]["position"]


def remove_from_waitlist(email):
    """Removes the user email from waitlist."""
    waitlist = load_json(db.get(WAITLIST_STORE))
    if email in waitlist:
        del waitlist[email]
        db.set(WAITLIST_STORE, dump_json(waitlist))
        logger.info(f"Removed {email} from waitlist")
        return True
    logger.info(f"Email {email} not found in waitlist")
    return False


def is_in_waitlist(email):
    """Checks if the user email is in the waitlist."""
    waitlist = load_json(db.get(WAITLIST_STORE))
    return email in waitlist


def recalculate_positions(waitlist_data):
    """Sorts the waitlist data and updates the 'position' field for all users."""
    if not waitlist_data:
        logger.info("No users in waitlist to recalculate positions.")
        return

    # Get a list of user data dictionaries
    users_list = list(waitlist_data.values())

    # Sort the list of users
    # Sort criteria:
    # 1. 'referrals' in descending order (-user['referrals'])
    # 2. 'joined_at' in ascending order (user['joined_at']) - for tie-breaking
    # Ensure 'joined_at' is comparable (e.g., ISO format strings work)
    sorted_users = sorted(
        users_list, key=lambda user: (-user["referrals"], user["joined_at"])
    )

    # Alternative and potentially better way: sort dictionary items directly
    sorted_items = sorted(
        waitlist_data.items(),  # Gives list of (email, user_data) tuples
        key=lambda item: (-item[1]["referrals"], item[1]["joined_at"]),
    )

    # Update positions in the original dictionary
    for i, (email, user_data) in enumerate(sorted_items):
        waitlist_data[email]["position"] = i + 1

    logger.info("Waitlist positions recalculated.")


def get_waitlist_position(email):
    """Returns the waitlist position of the user email."""
    waitlist = load_json(db.get(WAITLIST_STORE))
    if email in waitlist:
        return waitlist[email]["position"]
    return None


def get_full_waitlist():
    """
    Returns the full waitlist.
    Sorted by position.
    """
    waitlist = load_json(db.get(WAITLIST_STORE))
    users_list = list(waitlist.values())
    # Sort the users list by position
    sorted_users = sorted(
        users_list, key=lambda user: user.get("position", float("inf"))
    )

    return sorted_users


def get_email_by_referral_code(code):
    """Returns the email associated with the referral code."""
    refs = load_json(db.get(REFERRALS_STORE))
    for ref_code, email in refs.items():
        if ref_code == code:
            return email
    return None


def get_referral_code_from_email(email):
    """Returns the referral code of the user email."""
    refs = load_json(db.get(REFERRALS_STORE))
    return refs.get(email, None)


def get_referral_count(email):
    """Returns the referral count of the user email."""
    waitlist = load_json(db.get(WAITLIST_STORE))
    if email in waitlist:
        return waitlist[email]["referrals"]
    return 0
