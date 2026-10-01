from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from config.environment import DATABASE_URL
from data.user_data import user_list

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

try:
    print("Seeding the database...")

    db = SessionLocal()

    db.add_all(user_list)
    db.commit()

    db.close()

    print("Database seeding complete! 👋")

except Exception as e:
    print("An error occurred:", e)
