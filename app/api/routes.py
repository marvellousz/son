from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel, Field
from datetime import datetime

from app.database.session import get_db
from app.database import models

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime


class TodoResponse(BaseModel):
    id: int
    user_id: int
    title: str
    is_completed: bool
    completed_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class TodoCreate(BaseModel):
    telegram_id: int = Field(
        ..., description="The Telegram ID of the user creating the task"
    )
    title: str = Field(
        ..., min_length=1, max_length=500, description="The checklist description"
    )


class NoteResponse(BaseModel):
    id: int
    user_id: int
    content: str
    filepath: str
    category: str
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/health", response_model=HealthResponse)
def health_check() -> dict:
    """Simple API status checks endpoint."""
    return {"status": "ok", "timestamp": datetime.utcnow()}


@router.get("/todos", response_model=List[TodoResponse])
def get_all_todos(db: Session = Depends(get_db)) -> List[models.Todo]:
    """Retrieve all todo checklist items from SQLite database."""
    return db.query(models.Todo).order_by(models.Todo.created_at.desc()).all()


@router.post("/todo", response_model=TodoResponse, status_code=status.HTTP_201_CREATED)
def create_todo(payload: TodoCreate, db: Session = Depends(get_db)) -> models.Todo:
    """Expose todo creation programmatically via HTTP POST."""
    user = (
        db.query(models.User)
        .filter(models.User.telegram_id == payload.telegram_id)
        .first()
    )
    if not user:
        user = models.User(telegram_id=payload.telegram_id)
        db.add(user)
        db.commit()
        db.refresh(user)

    todo = models.Todo(user_id=user.id, title=payload.title)
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return todo


@router.get("/notes", response_model=List[NoteResponse])
def get_all_notes(db: Session = Depends(get_db)) -> List[models.Note]:
    """Retrieve all saved markdown note metadata from SQLite."""
    return db.query(models.Note).order_by(models.Note.created_at.desc()).all()
