# cleanup redis db

from database import db

keys = db.keys("*")

for key in keys:
    db.delete(key)
    print(f"Deleted key: {key}")

print(db.keys("*"))  # should be empty
print("All keys deleted from Redis database.")
