"""
db.py — SQLAlchemy database layer for the Grocery Agent.

Provides the engine, session factory, ORM table definitions, and helpers to
create tables. PostgreSQL is the target database; the connection string is read
from the DATABASE_URL environment variable.
"""

import os
import time

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    Date,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# Default points at a local Postgres; overridden via DATABASE_URL in Docker.
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://grocery:grocery@localhost:5432/grocery",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)
Base = declarative_base()


class ProductRow(Base):
    """A purchasable product in the catalogue."""

    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False, index=True)  # category key, e.g. "milk"
    brand = Column(String(120), nullable=False)
    unit = Column(String(120), nullable=False, default="")
    price = Column(Float, nullable=False, default=0.0)
    category = Column(String(120), nullable=False, default="")


class OrderRow(Base):
    """A single past order placed on a given date."""

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)

    items = relationship(
        "OrderItemRow",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class OrderItemRow(Base):
    """A line item belonging to an order."""

    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(120), nullable=False, index=True)
    brand = Column(String(120), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit = Column(String(120), nullable=False, default="")
    price = Column(Float, nullable=False, default=0.0)

    order = relationship("OrderRow", back_populates="items")


class BasketItemRow(Base):
    """An item currently in the user's basket."""

    __tablename__ = "basket_items"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    brand = Column(String(120), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit = Column(String(120), nullable=False, default="")
    price = Column(Float, nullable=False, default=0.0)


def wait_for_db(max_attempts: int = 30, delay: float = 1.0) -> None:
    """Block until the database accepts connections (useful at container start)."""
    from sqlalchemy import text

    last_err = None
    for _ in range(max_attempts):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except Exception as e:  # pragma: no cover - startup race handling
            last_err = e
            time.sleep(delay)
    raise RuntimeError(f"Database not reachable at {DATABASE_URL}: {last_err}")


def init_db() -> None:
    """Create all tables if they do not already exist."""
    Base.metadata.create_all(engine)
