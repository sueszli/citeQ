from enum import Enum


from transformers import pipeline
import tensorflow as tf
import torch as th


class SentimentLabel(Enum):
    NEGATIVE = 0
    POSITIVE = 1


class TransformerClassifier:
    @staticmethod
    def get_sentiment_score(text: str) -> tuple[SentimentLabel, float]:
        classifier = pipeline("text-classification", model="distilbert-base-uncased-finetuned-sst-2-english")
        result = classifier(text)
        assert result
        result = next(iter(result))
        label = result["label"]
        score = result["score"]
        if label == "NEGATIVE":
            label = SentimentLabel.NEGATIVE
        elif label == "POSITIVE":
            label = SentimentLabel.POSITIVE
        else:
            raise Exception("unknown label")
        return label, score
