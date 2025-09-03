// MongoDB 초기화 스크립트
// 뉴스 API용 데이터베이스 및 사용자 생성

// 데이터베이스 생성 및 선택
db = db.getSiblingDB('verachain_news');

// 애플리케이션 전용 사용자 생성
db.createUser({
  user: 'newsuser',
  pwd: 'newspass',
  roles: [
    {
      role: 'readWrite',
      db: 'verachain_news'
    }
  ]
});

// 기본 컬렉션 생성 및 인덱스 설정
db.createCollection('articles');
db.createCollection('user_profiles');
db.createCollection('user_activity');
db.createCollection('personalization_cache');

// 기사 컬렉션 인덱스
db.articles.createIndex({ "id": 1 }, { unique: true });
db.articles.createIndex({ "published": -1 });
db.articles.createIndex({ "collected_at": -1 });
db.articles.createIndex({ "source": 1 });

// 사용자 프로필 인덱스
db.user_profiles.createIndex({ "user_id": 1 }, { unique: true });

// 사용자 활동 인덱스
db.user_activity.createIndex({ "user_id": 1 });
db.user_activity.createIndex({ "timestamp": -1 });
db.user_activity.createIndex({ "article_id": 1 });

// 개인화 캐시 인덱스
db.personalization_cache.createIndex({ 
  "article_id": 1, 
  "user_id": 1 
}, { unique: true });
db.personalization_cache.createIndex({ "created_at": 1 });

// TTL 인덱스 (자동 만료) - 30일 후 자동 삭제
db.personalization_cache.createIndex(
  { "created_at": 1 }, 
  { expireAfterSeconds: 2592000 } // 30일 = 30 * 24 * 60 * 60
);

print('verachain_news 데이터베이스 초기화 완료');
print('사용자: newsuser');
print('컬렉션: articles, user_profiles, user_activity, personalization_cache');
print('인덱스 및 TTL 설정 완료');