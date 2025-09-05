import sqlite3
from datetime import datetime

def detailed_check():
    conn = sqlite3.connect('kkalkalnews.db')
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"Today: {today}")
    
    # Check user_activity table details
    print("\n=== USER ACTIVITY ===")
    cursor.execute("SELECT COUNT(*) FROM user_activity")
    total = cursor.fetchone()[0]
    print(f"Total user activities: {total}")
    
    cursor.execute("SELECT COUNT(*) FROM user_activity WHERE date(created_at) = ?", (today,))
    today_count = cursor.fetchone()[0]
    print(f"Today's activities: {today_count}")
    
    # Check recent activities
    cursor.execute("SELECT action, COUNT(*) FROM user_activity GROUP BY action LIMIT 10")
    actions = cursor.fetchall()
    print(f"Action types: {dict(actions)}")
    
    # Check personalized content
    print("\n=== PERSONALIZED CONTENT ===")
    cursor.execute("SELECT COUNT(*) FROM personalized_content")
    total = cursor.fetchone()[0]
    print(f"Total personalized content: {total}")
    
    cursor.execute("SELECT COUNT(*) FROM personalized_content WHERE date(created_at) = ?", (today,))
    today_count = cursor.fetchone()[0]
    print(f"Today's personalized content: {today_count}")
    
    # Check original articles
    print("\n=== ORIGINAL ARTICLES ===")
    cursor.execute("SELECT COUNT(*) FROM original_articles")
    total = cursor.fetchone()[0]
    print(f"Total original articles: {total}")
    
    cursor.execute("SELECT COUNT(*) FROM original_articles WHERE date(created_at) = ?", (today,))
    today_count = cursor.fetchone()[0]
    print(f"Today's articles: {today_count}")
    
    # Recent dates check
    print("\n=== RECENT ACTIVITY DATES ===")
    cursor.execute("SELECT date(created_at) as date, COUNT(*) FROM user_activity GROUP BY date(created_at) ORDER BY date DESC LIMIT 7")
    recent = cursor.fetchall()
    print("Recent user activity by date:")
    for date, count in recent:
        print(f"  {date}: {count}")
    
    cursor.execute("SELECT date(created_at) as date, COUNT(*) FROM personalized_content GROUP BY date(created_at) ORDER BY date DESC LIMIT 7")
    recent = cursor.fetchall()
    print("\nRecent personalized content by date:")
    for date, count in recent:
        print(f"  {date}: {count}")
    
    conn.close()

if __name__ == "__main__":
    detailed_check()