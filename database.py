import string
import random
import redis
import json
import logging
from typing import Optional

from config import Config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Redis connection
redis_client = redis.Redis(
    host=Config.REDIS_HOST,
    port=Config.REDIS_PORT,
    password=Config.REDIS_PASSWORD,
    username=Config.REDIS_USERNAME,
    decode_responses=True,
)


def generate_referral_code():
    code = None
    while code is None or is_referral_code_existing(code):
        characters = string.ascii_uppercase + string.digits
        code = "".join(random.choice(characters) for _ in range(5))
    return "ARC" + code


def add_to_waitlist(email, phone, referral_code=None):
    """
    Add a user to the waitlist with separate entries for user info and position.
    If referral_code is provided, adjust positions accordingly.
    """
    if not email:
        return False

    try:
        # Get users in a way that handles both formats
        users = get_users()
        if email in users:
            return False

        # Generate new referral code for the user
        new_referral_code = generate_referral_code()

        # Create user info entry
        user_info = {
            "email": email,
            "phone": phone,
            "referral_code": new_referral_code,
            "referrals": 0,  # Initialize referral count
            "referred_by": referral_code,  # Track who referred this user
            "referred_by_email": (
                get_email_by_referral_code(referral_code) if referral_code else None
            ),
        }

        # Add user info to users
        users[email] = user_info
        redis_client.set("users", json.dumps(users))

        # Add to waitlist positions
        waitlist = get_waitlist_positions()
        if email not in waitlist:
            # Get the next position number
            next_position = len(waitlist) + 1
            waitlist[email] = next_position
            redis_client.set("waitlist_positions", json.dumps(waitlist))

        # Add referral code mapping
        add_referral_code(new_referral_code, email)

        # If referral code was used, adjust positions and increment referral count
        if referral_code:
            adjust_positions_for_referral(referral_code)
            increment_referral_count(referral_code)

        return True
    except Exception as e:
        logger.error(f"Error in add_to_waitlist: {str(e)}")
        # If there's an error, try to clean up any partial data
        try:
            users = get_users()
            if email in users:
                del users[email]
                redis_client.set("users", json.dumps(users))

            waitlist = get_waitlist_positions()
            if email in waitlist:
                del waitlist[email]
                redis_client.set("waitlist_positions", json.dumps(waitlist))
        except:
            pass
        return False


def increment_referral_count(referral_code):
    """
    Increment the referral count for the user who owns this referral code.
    """
    referrer_email = get_email_by_referral_code(referral_code)
    if not referrer_email:
        return False

    users = get_users()
    if referrer_email in users:
        users[referrer_email]["referrals"] = (
            users[referrer_email].get("referrals", 0) + 1
        )
        redis_client.set("users", json.dumps(users))
        return True
    return False


def get_referral_count(email):
    """
    Get the number of referrals for a user.
    """
    users = get_users()
    if email in users:
        return users[email].get("referrals", 0)
    return 0


def adjust_positions_for_referral(referral_code):
    """
    Adjust waitlist positions when someone uses a referral code.
    Moves the referrer one position up only if they have more referrals than the person before them.
    """
    # Get the referrer's email
    referrer_email = get_email_by_referral_code(referral_code)
    if not referrer_email:
        return False

    waitlist = get_waitlist_positions()
    users = get_users()

    # Get current positions
    referrer_position = waitlist[referrer_email]

    # Find the person before the referrer
    person_before = None
    for email, position in waitlist.items():
        if position == referrer_position - 1:
            person_before = email
            break

    # Check referral counts before swapping
    if person_before:
        referrer_count = users[referrer_email].get("referrals", 0)
        person_before_count = users[person_before].get("referrals", 0)

        # Only swap if referrer has more referrals
        if referrer_count > person_before_count:
            # Move person before down one position
            waitlist[person_before] = referrer_position
            # Move referrer up one position
            waitlist[referrer_email] = referrer_position - 1
            redis_client.set("waitlist_positions", json.dumps(waitlist))
            return True

    return False


def cleanup_redis_data():
    """Clean up Redis data to ensure consistent format"""
    try:
        # Check and clean users data
        try:
            redis_client.get("users")
        except redis.ResponseError:
            # If it's a hash, convert to string
            users_data = redis_client.hgetall("users")
            users = {}
            for email, user_json in users_data.items():
                try:
                    user_data = json.loads(user_json)
                    users[email] = user_data
                except:
                    continue
            redis_client.delete("users")
            redis_client.set("users", json.dumps(users))

        # Check and clean waitlist positions
        try:
            redis_client.get("waitlist_positions")
        except redis.ResponseError:
            # If it's a hash, convert to string
            positions = redis_client.hgetall("waitlist_positions")
            positions_dict = {
                email: int(position) for email, position in positions.items()
            }
            redis_client.delete("waitlist_positions")
            redis_client.set("waitlist_positions", json.dumps(positions_dict))

        # Check and clean referral codes
        try:
            redis_client.get("referral_codes")
        except redis.ResponseError:
            # If it's a hash, convert to string
            codes = redis_client.hgetall("referral_codes")
            redis_client.delete("referral_codes")
            redis_client.set("referral_codes", json.dumps(codes))

    except Exception as e:
        logger.error(f"Error in cleanup_redis_data: {str(e)}")
        # If cleanup fails, try to delete all keys
        try:
            redis_client.delete("users")
            redis_client.delete("waitlist_positions")
            redis_client.delete("referral_codes")
        except:
            pass


def get_users():
    """
    Get all users information from Redis.
    """
    try:
        cleanup_redis_data()  # Ensure data is in correct format
        users_data = redis_client.get("users")
        if users_data is None:
            return {}
        users = eval(users_data)

        # Ensure referred_by_email is set for all users
        for email, user_info in users.items():
            if user_info.get("referred_by") and not user_info.get("referred_by_email"):
                user_info["referred_by_email"] = get_email_by_referral_code(
                    user_info["referred_by"]
                )

        return users
    except Exception as e:
        logger.error(f"Error in get_users: {str(e)}")
        # If error persists, try to reset the data
        try:
            redis_client.delete("users")
            redis_client.set("users", json.dumps({}))
            return {}
        except:
            return {}


def get_waitlist_positions():
    """
    Get the waitlist positions from Redis.
    """
    try:
        cleanup_redis_data()  # Ensure data is in correct format
        positions_data = redis_client.get("waitlist_positions")
        if positions_data is None:
            return {}
        return eval(positions_data)
    except Exception as e:
        logger.error(f"Error in get_waitlist_positions: {str(e)}")
        # If error persists, try to reset the data
        try:
            redis_client.delete("waitlist_positions")
            redis_client.set("waitlist_positions", json.dumps({}))
            return {}
        except:
            return {}


def get_user_position(email):
    """
    Get a user's position in the waitlist.
    """
    waitlist = get_waitlist_positions()
    return waitlist.get(email)


def remove_from_waitlist(email):
    """
    Remove a user from both users list and waitlist positions.
    """
    if not email:
        return False

    # Get user's referral code before removing
    users = get_users()
    if email in users:
        referral_code = users[email]["referral_code"]
        del users[email]
        redis_client.set("users", json.dumps(users))

        # Remove referral code mapping
        referral_codes = get_referral_codes()
        if referral_code in referral_codes:
            del referral_codes[referral_code]
            redis_client.set("referral_codes", json.dumps(referral_codes))

    # Remove from waitlist positions
    waitlist = get_waitlist_positions()
    if email in waitlist:
        position = waitlist[email]
        del waitlist[email]

        # Reorder remaining positions
        for key in waitlist:
            if waitlist[key] > position:
                waitlist[key] = waitlist[key] - 1

        redis_client.set("waitlist_positions", json.dumps(waitlist))
        return True

    return False


def get_waitlist_size():
    """
    Get the total number of users in the waitlist.
    """
    waitlist = get_waitlist_positions()
    return len(waitlist)


def get_referral_codes():
    """
    Get all referral codes and their associated emails.
    """
    try:
        cleanup_redis_data()  # Ensure data is in correct format
        codes = redis_client.get("referral_codes")
        if codes is None:
            return {}
        return eval(codes)
    except Exception as e:
        logger.error(f"Error in get_referral_codes: {str(e)}")
        # If error persists, try to reset the data
        try:
            redis_client.delete("referral_codes")
            redis_client.set("referral_codes", json.dumps({}))
            return {}
        except:
            return {}


def add_referral_code(referral_code, email):
    """
    Add a referral code with associated email to Redis.
    """
    codes = get_referral_codes()
    codes[referral_code] = email
    redis_client.set("referral_codes", json.dumps(codes))
    return True


def is_referral_code_existing(code):
    """
    Check if a referral code exists.
    """
    if code is None:
        return False
    codes = get_referral_codes()
    return code in codes


def get_email_by_referral_code(code):
    """
    Get the email associated with a referral code.
    """
    codes = get_referral_codes()
    return codes.get(code)


def get_referred_by(email):
    """Get who referred a specific user"""
    users = get_users()
    if email in users:
        user_info = users[email]
        referral_code = user_info.get("referred_by")
        if referral_code:
            return get_email_by_referral_code(referral_code)
    return None


def get_referral_code_from_email(email):
    """Get the referral code associated with a specific email"""
    users = get_users()
    if email in users:
        return users[email].get("referral_code")
    return None
