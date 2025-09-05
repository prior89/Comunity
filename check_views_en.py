import sqlite3
from datetime import datetime

def check_todays_news_views():
    conn = sqlite3.connect('kkalkalnews.db')
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("Available tables:", [t[0] for t in tables])
    
    # Today's date
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"\nToday: {today}")
    
    try:
        # Check user_activity table for today's views
        cursor.execute("PRAGMA table_info(user_activity)")
        columns = cursor.fetchall()
        print(f"\nuser_activity columns: {[col[1] for col in columns]}")
        
        # Count today's activities
        cursor.execute("SELECT COUNT(*) FROM user_activity WHERE date(created_at) = ?", (today,))
        count = cursor.fetchone()[0]
        print(f"Today's user activities: {count}")
        
        # Check activity types
        cursor.execute("SELECT activity_type, COUNT(*) FROM user_activity WHERE date(created_at) = ? GROUP BY activity_type", (today,))
        activities = cursor.fetchall()
        print(f"Activity breakdown: {dict(activities)}")
        
        # Check personalized_content table
        cursor.execute("PRAGMA table_info(personalized_content)")
        columns = cursor.fetchall()
        print(f"\npersonalized_content columns: {[col[1] for col in columns]}")
        
        cursor.execute("SELECT COUNT(*) FROM personalized_content WHERE date(created_at) = ?", (today,))
        count = cursor.fetchone()[0]
        print(f"Today's personalized content: {count}")
        
        # Check original_articles table
        cursor.execute("SELECT COUNT(*) FROM original_articles WHERE date(created_at) = ?", (today,))
        count = cursor.fetchone()[0]
        print(f"Today's original articles: {count}")
        
    except Exception as e:
        print(f"Error: {e}")
    
    conn.close()

if __name__ == "__main__":
    check_todays_news_views()