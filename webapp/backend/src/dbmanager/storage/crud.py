"""
CRUD helpers for dashboard configuration.
"""

from __future__ import annotations

from typing import TypeVar

from sqlalchemy.orm import Session

from .database import Base

ModelT = TypeVar("ModelT", bound=Base)


def get_or_create_singleton(session: Session, model: type[ModelT]) -> ModelT:
    instance = session.query(model).first()
    if instance is None:
        instance = model()
        session.add(instance)
        session.commit()
        session.refresh(instance)
    return instance


def update_model(instance: ModelT, payload: dict) -> ModelT:
    for key, value in payload.items():
        if hasattr(instance, key):
            setattr(instance, key, value)
    return instance
