from db import Researcher, Paper, Authorship, Citation, engine
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import random
from enum import Enum
from tqdm import tqdm


class SentimentClass(Enum):
    CRITICIZING = 0
    COMPARISON = 1
    USE = 2
    SUBSTANTIATING = 3
    BASIS = 4
    NEUTRAL_OR_UNKNOWN = 5


# Create a session to use the tables
session = Session(engine)

# Update the citation purposes with the llm output
with open("llm_purpose_5.csv", "r") as f:
    citations = f.readlines()
    for citation in tqdm(citations):
        c_id, annotation = citation.split(",")
        c_id = int(c_id)
        citation = session.query(Citation).filter(Citation.id == c_id).first()
        citation.llm_purpose = annotation.strip()
        session.commit()

    session.close()
