import sys
from database import SessionLocal, engine, Base
from app.models.user import User
from app.core.security import hash_password

if len(sys.argv) < 4:
    print('Cách dùng: python create_user.py <username> <password> "<họ tên>"')
    sys.exit(1)

username, password, full_name = sys.argv[1], sys.argv[2], sys.argv[3]
Base.metadata.create_all(bind=engine)
with SessionLocal() as db:
    if db.query(User).filter(User.username == username).first():
        print("Username đã tồn tại")
        sys.exit(1)
    db.add(User(username=username, password_hash=hash_password(password), full_name=full_name, role="analyst"))
    db.commit()
    print("Đã tạo tài khoản", username)
