from db import Researcher, Paper, Authorship, Citation, engine
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import random
from tqdm import tqdm

from llm_classifier import LlmClassifier, SentimentClass

# load environment variables
import os
from dotenv import load_dotenv

load_dotenv()

# Create a session to use the tables
session = Session(engine)

# Read the already annotated citations
annotated_citations = []
with open("citations_annotated.csv", "r") as f:
    citations = f.readlines()
    for citation in citations:
        annotated_citations.append(citation.strip().split(","))

# get the llm annotations
llm_annotations = []
for citation in tqdm(annotated_citations):
    citation_context = session.query(Citation).filter(Citation.id == citation[0]).first().context
    predicted_class = LlmClassifier.get_sentiment_class(citation_context, "llama")
    llm_annotations.append([citation[0], int(citation[1] if citation[1] != 3 else "2"), predicted_class.value])

# write the llm annotations to a file
with open("llm_annotations_llama.csv", "w") as f:
    for annotation in llm_annotations:
        f.write(f"{annotation[0]},{annotation[1]},{annotation[2]}\n")

# calculate precision, and recall for each class
tp = [0, 0, 0, 0]
fp = [0, 0, 0, 0]
fn = [0, 0, 0, 0]

for annotation in llm_annotations:
    if annotation[1] == annotation[2]:
        tp[annotation[1]] += 1
    else:
        fp[annotation[2]] += 1
        fn[annotation[1]] += 1

precision = [0, 0, 0, 0]
recall = [0, 0, 0, 0]
for i in range(4):
    precision[i] = tp[i] / (tp[i] + fp[i]) if tp[i] + fp[i] != 0 else 0
    recall[i] = tp[i] / (tp[i] + fn[i])

print(f"Precision: {precision}")
print(f"Recall: {recall}")
