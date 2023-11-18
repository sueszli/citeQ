# todo:
# - make this an independent module
# - give sentiment class (based on https://aclanthology.org/N13-1067.pdf)
# - give ability to process pdf (optional, just out of curiosity)


from enum import Enum

from transformers import pipeline
import tensorflow as tf
import torch as th


class SentimentScoreLabel(Enum):
    NEGATIVE = 0
    POSITIVE = 1


class NatualLanguageProcessor:
    @staticmethod
    def get_sentiment_score(text: str) -> tuple[SentimentScoreLabel, float]:
        classifier = pipeline("text-classification", model="distilbert-base-uncased-finetuned-sst-2-english")
        result = classifier(text)
        assert result
        result = next(iter(result))
        label = result["label"]
        score = result["score"]
        if label == "NEGATIVE":
            label = SentimentScoreLabel.NEGATIVE
        elif label == "POSITIVE":
            label = SentimentScoreLabel.POSITIVE
        else:
            raise Exception("unknown label")
        return label, score


if __name__ == "__main__":
    print(NatualLanguageProcessor.get_sentiment_score("what a great day!"))
