"""
Database loader helpers
"""
import json


def load_json(string):
    """Load the str object from redis as a JSON object."""
    if not string:
        return {}
    try:
        return json.loads(string)
    except json.JSONDecodeError:
        return {}


def dump_json(obj):
    """Dump the JSON object to a str object."""
    if not obj:
        return "{}"
    try:
        return json.dumps(obj)
    except TypeError:
        return "{}"
