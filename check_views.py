import sqlite3
from datetime import datetime, timedelta

def check_todays_news_views():
    conn = sqlite3.connect('kkalkalnews.db')
    cursor = conn.cursor()
    
    # 테이블 확인
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("사용 가능한 테이블:", [t[0] for t in tables])
    
    # 오늘 날짜
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"\n오늘 날짜: {today}")
    
    try:
        # 뉴스 조회 관련 테이블 확인
        for table in ['news', 'articles', 'user_activity', 'news_views', 'analytics']:
            try:
                cursor.execute(f"SELECT * FROM {table[0]} LIMIT 1")
                print(f"\n{table[0]} 테이블 존재")
                
                # 테이블 구조 확인
                cursor.execute(f"PRAGMA table_info({table[0]})")
                columns = cursor.fetchall()
                print(f"컬럼: {[col[1] for col in columns]}")
                
                # 오늘 데이터 확인
                if 'created_at' in [col[1] for col in columns]:
                    cursor.execute(f"SELECT COUNT(*) FROM {table[0]} WHERE date(created_at) = ?", (today,))
                    count = cursor.fetchone()[0]
                    print(f"오늘 {table[0]} 수: {count}")
                elif 'timestamp' in [col[1] for col in columns]:
                    cursor.execute(f"SELECT COUNT(*) FROM {table[0]} WHERE date(timestamp) = ?", (today,))
                    count = cursor.fetchone()[0]
                    print(f"오늘 {table[0]} 수: {count}")
                    
            except sqlite3.OperationalError:
                continue
                
    except Exception as e:
        print(f"오류: {e}")
    
    conn.close()

if __name__ == "__main__":
    check_todays_news_views()