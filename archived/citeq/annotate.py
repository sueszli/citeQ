from db import Researcher, Paper, Authorship, Citation, engine
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import random
from enum import Enum


class SentimentClass(Enum):
    POSITIVE = 0
    NEGATIVE = 1
    NEUTRAL = 2
    BAD_CONTEXT = 3


# Create a session to use the tables
session = Session(engine)

# Read the already annotated citations
annotated_citations = []
with open("citations_annotated.csv", "r") as f:
    citations = f.readlines()
    for citation in citations:
        annotated_citations.append(citation.split(",")[0])

total_annotation = 100

for i in range(len(annotated_citations), total_annotation):
    citation = session.query(Citation).order_by(random()).first()
    while citation.id in annotated_citations:
        citation = session.query(Citation).order_by(random()).first()

    print(f"---------- Citation: {i} ----------\n")
    print(citation.context + "\n")
    print("--------------------\n")
    print("0: POSITIVE\n1: NEGATIVE\n2: NEUTRAL\n3: BAD_CONTEXT\n")

    annotation = input("Annotation: ")
    while annotation not in ["0", "1", "2", "3", "exit", "skip"]:
        annotation = input("Annotation: ")

    if annotation == "exit":
        break
    elif annotation == "skip":
        continue
    with open("citations_annotated.csv", "a") as f:
        f.write(f"{citation.id},{annotation}\n")
