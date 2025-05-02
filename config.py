from decouple import config
import logging


class Config:

    try:
        REDIS_HOST = config("REDIS_HOST")
        REDIS_PORT = config("REDIS_PORT", cast=int)
        REDIS_USERNAME = config("REDIS_USERNAME", default=None)
        REDIS_PASSWORD = config("REDIS_PASSWORD", default=None)
        EMAIL_SENDER = config("EMAIL_SENDER")
        EMAIL_PASSWORD = config("EMAIL_PASSWORD")
    except Exception as e:
        logging.warning("Error loading configurations: %s", e)
        logging.info("Make sure to set the environment variables correctly.")
        exit(1)
