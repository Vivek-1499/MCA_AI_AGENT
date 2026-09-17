import sqlite3
import os
import shutil

# Clear SQLite DB
conn = sqlite3.connect("processed_docs.db")
cursor = conn.cursor()
cursor.execute("DELETE FROM processed_documents")
conn.commit()
conn.close()

# Clear storage directory
if os.path.exists("storage"):
    shutil.rmtree("storage")
os.makedirs("storage", exist_ok=True)

# Clear temp_downloads
if os.path.exists("temp_downloads"):
    shutil.rmtree("temp_downloads")
os.makedirs("temp_downloads", exist_ok=True)

print("Database, storage, and temp_downloads directories fully cleared!")
