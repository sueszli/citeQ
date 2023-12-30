from db import Researcher, Paper, Authorship, Citation, engine
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import random
from enum import Enum
from tqdm import tqdm


class SentimentClass(Enum):
    POSITIVE = 0
    NEGATIVE = 1
    NEUTRAL = 2
    BAD_CONTEXT = 3


# Create a session to use the tables
session = Session(engine)
path = "llm_purpose_649000_697609.csv"
print(f"Reading {path}...")
# Update the citation purposes with the llm output
with open(path, "r") as f:
    citations = f.readlines()
    for citation in tqdm(citations):
        c_id, annotation = citation.split(",")
        c_id = int(c_id)
        citation = session.query(Citation).filter(Citation.id == c_id).first()
        citation.llm_purpose = annotation.strip()
        session.commit()

    session.close()
