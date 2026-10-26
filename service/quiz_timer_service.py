import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from databaseModel.quiz_model import Quiz
from database_config import SessionLocal

async def handle_quiz_timer(quiz_id: int, duration_minutes: int):
    """
    Background worker that waits for the specified duration,
    then automatically stops the quiz in the database.
    """
    # Convert minutes to seconds
    await asyncio.sleep(duration_minutes * 60)
    
    # Open a fresh database session for the background task
    db: Session = SessionLocal()
    try:
        quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
        if quiz and quiz.is_start:
            quiz.is_start = False
            db.commit()
            print(f"[Background Service] Quiz ID {quiz_id} time expired. Automatically stopped.")
    except Exception as e:
        db.rollback()
        print(f"[Background Service Error] Failed to auto-stop quiz {quiz_id}: {str(e)}")
    finally:
        db.close()