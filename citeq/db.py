import sqlalchemy
from sqlalchemy import create_engine, Date
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey
from typing import Optional
import datetime
import os

engine = create_engine("sqlite+pysqlite:///./citeQ.db")


class Base(DeclarativeBase):
    pass


class Researcher(Base):
    __tablename__ = "researchers"

    id: Mapped[int] = mapped_column(primary_key=True)
    semantic_scholar_id: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    h_index: Mapped[int]
    institution: Mapped[Optional[str]]


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(primary_key=True)
    semantic_scholar_id: Mapped[str] = mapped_column(unique=True)
    title: Mapped[str]
    year: Mapped[Optional[int]]
    venue: Mapped[Optional[str]]
    citation_count: Mapped[Optional[int]]
    doi: Mapped[Optional[str]]


class Authorship(Base):
    __tablename__ = "authorships"

    id: Mapped[int] = mapped_column(primary_key=True)
    researcher_id: Mapped[int] = mapped_column(ForeignKey("researchers.id"))
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"))
    author_order: Mapped[int]


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[int] = mapped_column(primary_key=True)
    citing_paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"))
    cited_paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"))
    context: Mapped[str]
    intent: Mapped[str]
    llm_purpose: Mapped[Optional[str]]
    sentiment: Mapped[Optional[str]]


if os.path.exists("./citeQ.db"):
    print("Database already exists")
else:
    Base.metadata.create_all(engine)
