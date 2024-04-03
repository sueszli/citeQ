from enum import Enum

from logger import LOG_SINGLETON as LOG, trace

from thefuzz import fuzz
from langchain.llms import Ollama

from langchain_community.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
import backoff
import random

import os

os.environ["OPENAI_API_KEY"] = ""

PROMPT = """
The following is a set of citation purpose categories, each category name is followed by a description of the category and an example of a sentence that belongs to this category.

Name: Criticizing
Description: A citing sentence is classified as "criticizing" when it mentions the weakness of the cited approach, negatively criticizes the cited approach, negatively evaluates the cited source.
Example: Chiang (2005) introduced a constituent feature to reward phrases that match a syntactic tree but did not yield significant improvement.

Name: Comparison
Description: A citing sentence is classified as "comparison" when it compares or contrasts the work in the cited paper to the author's work. It overlaps with the first category when the citing sentence says one approach is not as good as the other approach. In this case we use the first category.
Example: Our approach permits an alternative to minimum error-rate training (MERT; Och, 2003);

Name: Use
Description: A citing sentence is classified as "use" when the citing paper uses the method, idea or tool of the cited paper.
Example: We perform the MERT training (Och, 2003) to tune the optimal feature weights on the development set.

Name: Substantiating
Description: A citing sentence is classified as "substantiating" when the results, claims of the citing work substantiate, verify the cited paper and support each other.
Example: It was found to produce automated scores, which strongly correlate with human judgements about translation fluency (Papineni et al. , 2002).

Name: Basis
Description: A citing sentence is classified as "basis" when the author uses the cited work as starting point or motivation and extends on the cited work.
Example: Our model is derived from the hidden-markov model for word alignment (Vogel et al., 1996; Och and Ney, 2000).

Name: Neutral (Other)
Description: A citing sentence is classified as "neutral" when it is a neutral description of the cited work or if it doesn't come under any of the above categories.
Example: The solutions of these problems depend heavily on the quality of the word alignment (Och and Ney, 2000).

Classify the following in text citation into one of these categories. Respond with only a single word, the name of the category.

"""

PROMPT_2 = """
The following is a set of citation sentiment categories, each category name is followed by a description of the category and some examples of in-text citation contexts that belongs to this category.

Name: Positive
Description: A citing sentence is classified as "positive" when it mentions the strength of the cited approach, positively criticizes the cited approach, positively evaluates the cited source, uses the cited source as a starting point or motivation and extends on the cited work, or when the results, claims of the citing work substantiate, verify the cited paper and support each other.
Example 1: Researchers [13] have presented a Secure and Efficient Topology Discovery Protocol (sOFTDP) that shifts a part of the link discovery to the SDN switch.
Example 2: To obtain more precise and descriptive topics, we further conducted GuidedLDA [24] using some of the most salient keywords selected from our initial LDA results.

Name: Negative
Description: A citing sentence is classified as "negative" when it mentions the weakness of the cited approach, negatively criticizes the cited approach, negatively evaluates the cited source.
Example 1: Most of the existing literature on the execution cost problem focus on markets where only one investor trades (for instance see [3, 4, 5, 6, 8, 9]).
Example 2: With nonlinear CI test, LPCMCI is computationally too expensive to be compared when the number of nodes is large.

Name: Neutral
Description: A citing sentence is classified as "neutral" when it is a neutral description of the cited work. Use this category when there is no strong criticism negatively or positively.
Example 1: Since the inception of spam, many companies and research teams have combined their efforts to fight against spam deliveries using different approaches and methods [1].
Example 2: Conventional approaches adopt fine-tuned generative models (Zhong et al., 2020b; Guo et al., 2021; Wang et al., 2021a, inter alia ) as input generators, with a semantic parser (e.g., PCFG grammar) for sampling symbolic outputs.

Name: Bad Context
Description: A citing sentence is classified as "bad context" when the given context is not enough to classify the citation or it does not include any citation.
Example 1: But then, the sum of welfare lost + retained is the optimum welfare and is bounded.
Example 2: Furthermore, since step (4) did not return FAIL, we must have g; a divisor of all entries in V' and W' hence JV contains only polynomial entries.

Classify the following in text citation into one of these categories. First, type 'THINKING:' and write your reasoining step by step. Then type 'ANSWER:' and give your answer in a single word.

"""
PROMPT_2_INST = """<s>[INST]
The following is a set of citation sentiment categories, each category name is followed by a description of the category and some examples of in-text citation contexts that belongs to this category.

Name: Positive
Description: A citing sentence is classified as "positive" when it mentions the strength of the cited approach, positively criticizes the cited approach, positively evaluates the cited source, uses the cited source as a starting point or motivation and extends on the cited work, or when the results, claims of the citing work substantiate, verify the cited paper and support each other.
Example 1: Researchers [13] have presented a Secure and Efficient Topology Discovery Protocol (sOFTDP) that shifts a part of the link discovery to the SDN switch.
Example 2: To obtain more precise and descriptive topics, we further conducted GuidedLDA [24] using some of the most salient keywords selected from our initial LDA results.

Name: Negative
Description: A citing sentence is classified as "negative" when it mentions the weakness of the cited approach, negatively criticizes the cited approach, negatively evaluates the cited source.
Example 1: Most of the existing literature on the execution cost problem focus on markets where only one investor trades (for instance see [3, 4, 5, 6, 8, 9]).
Example 2: With nonlinear CI test, LPCMCI is computationally too expensive to be compared when the number of nodes is large.

Name: Neutral
Description: A citing sentence is classified as "neutral" when it is a neutral description of the cited work. Use this category when there is no strong criticism negatively or positively.
Example 1: Since the inception of spam, many companies and research teams have combined their efforts to fight against spam deliveries using different approaches and methods [1].
Example 2: Conventional approaches adopt fine-tuned generative models (Zhong et al., 2020b; Guo et al., 2021; Wang et al., 2021a, inter alia ) as input generators, with a semantic parser (e.g., PCFG grammar) for sampling symbolic outputs.

Name: Bad Context
Description: A citing sentence is classified as "bad context" when the given context is not enough to classify the citation or it does not include any citation.
Example 1: But then, the sum of welfare lost + retained is the optimum welfare and is bounded.
Example 2: Furthermore, since step (4) did not return FAIL, we must have g; a divisor of all entries in V' and W' hence JV contains only polynomial entries.

Classify the following in text citation into one of these categories. First, type 'THINKING:' and write your reasoining step by step. Then type 'ANSWER:' and give your answer in a single word.

"""

PROMPT_3 = """
The following is a set of citation sentiment categories, each category name is followed by a description of the category and some examples of in-text citation contexts that belongs to this category.

Name: Positive
Description: A citing sentence is classified as "positive" when it mentions the strength of the cited approach, positively criticizes the cited approach, positively evaluates the cited source, uses the cited source as a starting point or motivation and extends on the cited work, or when the results, claims of the citing work substantiate, verify the cited paper and support each other.
Example 1: Researchers [13] have presented a Secure and Efficient Topology Discovery Protocol (sOFTDP) that shifts a part of the link discovery to the SDN switch.
Example 2: To obtain more precise and descriptive topics, we further conducted GuidedLDA [24] using some of the most salient keywords selected from our initial LDA results.

Name: Negative
Description: A citing sentence is classified as "negative" when it mentions the weakness of the cited approach, negatively criticizes the cited approach, negatively evaluates the cited source.
Example 1: Most of the existing literature on the execution cost problem focus on markets where only one investor trades (for instance see [3, 4, 5, 6, 8, 9]).
Example 2: With nonlinear CI test, LPCMCI is computationally too expensive to be compared when the number of nodes is large.

Name: Neutral
Description: A citing sentence is classified as "neutral" when it is a neutral description of the cited work. Use this category when there is no strong criticism negatively or positively.
Example 1: Since the inception of spam, many companies and research teams have combined their efforts to fight against spam deliveries using different approaches and methods [1].
Example 2: Conventional approaches adopt fine-tuned generative models (Zhong et al., 2020b; Guo et al., 2021; Wang et al., 2021a, inter alia ) as input generators, with a semantic parser (e.g., PCFG grammar) for sampling symbolic outputs.

Classify the following in text citation into one of these categories. First, type 'THINKING:' and write your reasoining step by step. Then type 'ANSWER:' and give your answer in a single word.

"""

PROMPT_3_INST = """<s>[INST]
The following is a set of citation sentiment categories, each category name is followed by a description of the category and some examples of in-text citation contexts that belongs to this category.

Name: Positive
Description: A citing sentence is classified as "positive" when it mentions the strength of the cited approach, positively criticizes the cited approach, positively evaluates the cited source, uses the cited source as a starting point or motivation and extends on the cited work, or when the results, claims of the citing work substantiate, verify the cited paper and support each other.
Example 1: Researchers [13] have presented a Secure and Efficient Topology Discovery Protocol (sOFTDP) that shifts a part of the link discovery to the SDN switch.
Example 2: To obtain more precise and descriptive topics, we further conducted GuidedLDA [24] using some of the most salient keywords selected from our initial LDA results.

Name: Negative
Description: A citing sentence is classified as "negative" when it mentions the weakness of the cited approach, negatively criticizes the cited approach, negatively evaluates the cited source.
Example 1: Most of the existing literature on the execution cost problem focus on markets where only one investor trades (for instance see [3, 4, 5, 6, 8, 9]).
Example 2: With nonlinear CI test, LPCMCI is computationally too expensive to be compared when the number of nodes is large.

Name: Neutral
Description: A citing sentence is classified as "neutral" when it is a neutral description of the cited work. Use this category when there is no strong criticism negatively or positively.
Example 1: Since the inception of spam, many companies and research teams have combined their efforts to fight against spam deliveries using different approaches and methods [1].
Example 2: Conventional approaches adopt fine-tuned generative models (Zhong et al., 2020b; Guo et al., 2021; Wang et al., 2021a, inter alia ) as input generators, with a semantic parser (e.g., PCFG grammar) for sampling symbolic outputs.

Classify the following in text citation into one of these categories. First, type 'THINKING:' and write your reasoining step by step. Then type 'ANSWER:' and give your answer in a single word.

"""


# class SentimentClass(Enum):
#     CRITICIZING = 0
#     COMPARISON = 1
#     USE = 2
#     SUBSTANTIATING = 3
#     BASIS = 4
#     NEUTRAL_OR_UNKNOWN = 5
def normalize_gpt(gpt):
    @backoff.on_exception(backoff.expo, Exception, max_tries=10)
    def res_gpt(input):
        messages = [
            SystemMessage(content="You are a helpful assistant that specialise in computer science."),
            HumanMessage(content=input),
        ]
        return gpt(messages).content

    return res_gpt


class SentimentClass(Enum):
    POSITIVE = 0
    NEGATIVE = 1
    NEUTRAL = 2
    BAD_CONTEXT = 3


class LlmClassifier:
    llm_mistral = Ollama(model="mistral")
    llm_llama = Ollama(model="llama2")
    llm_gpt = None  # normalize_gpt(ChatOpenAI(model="gpt-3.5-turbo-1106"))
    llm_gpt4 = None  # normalize_gpt(ChatOpenAI(model="gpt-4"))
    LLM = {"mistral": llm_mistral, "gpt3": llm_gpt, "gpt4": llm_gpt4, "llama": llm_llama}
    promt_printed = False

    @staticmethod
    def get_sentiment_class(citation: str, llm_type: str) -> SentimentClass:
        if llm_type == "random":
            return SentimentClass(random.randint(0, 3))

        prompt = PROMPT_2_INST + citation + "[/INST]" if llm_type == "mistral" else PROMPT_2 + citation
        if not LlmClassifier.promt_printed:
            print(prompt)
            LlmClassifier.promt_printed = True

        response: str = LlmClassifier.LLM[llm_type](prompt)

        while "ANSWER:" not in response:
            LOG.info(f"trying again: '{response}'")
            response = LlmClassifier.LLM[llm_type](prompt)

        answer = response.split("ANSWER:")[1].strip().lower()

        match = [
            (SentimentClass.POSITIVE, fuzz.partial_ratio(answer, "positive")),
            (SentimentClass.NEGATIVE, fuzz.partial_ratio(answer, "negative")),
            (SentimentClass.NEUTRAL, fuzz.partial_ratio(answer, "neutral")),
            (SentimentClass.BAD_CONTEXT, fuzz.partial_ratio(answer, "bad")),
        ]
        enum_match = max(match, key=lambda x: x[1])[0]
        # LOG.info(f"llm result: '{response}' → '{enum_match}', citation: '{citation}'")
        return enum_match
