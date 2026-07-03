import sqlite3

def migrate():
    conn = sqlite3.connect('instance/database.db') # or wherever database.db is stored
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE user ADD COLUMN name VARCHAR(150);")
        cursor.execute("ALTER TABLE user ADD COLUMN address TEXT;")
        cursor.execute("ALTER TABLE user ADD COLUMN contact_no VARCHAR(50);")
        cursor.execute("ALTER TABLE user ADD COLUMN profile_prompt_dismissed BOOLEAN DEFAULT 0;")
        conn.commit()
        print("User table migrated successfully!")
    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
