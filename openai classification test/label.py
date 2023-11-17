# import json
# import argparse
# import os
# import openai
# import time

# def get_args():
#     parser = argparse.ArgumentParser(description='Process args')
#     parser.add_argument('api_key', type=str, help='OpenAI API key')
#     parser.add_argument('file_path', type=str, help='Path to the JSONL file to process')
#     return parser.parse_args()

# def read_string_from_jsonl(file_path):
#     with open(file_path, 'r', encoding='utf-8') as file:
#         for line in file:
#             data = json.loads(line)
#             yield data["string"], data

# rules = extracted_text = """
# Category

# Description

# Example

# Criticizing

# Criticism can be positive or negative. A citing sentence is classified as “criticizing” when it mentions the weakness/strengths of the cited approach, negatively/positively criticizes the cited approach, negatively/positively evaluates the cited source.

# Chiang (2005) introduced a constituent feature to reward phrases that match a syntactic tree but did not yield significant improvement.

# Comparison

# A citing sentence is classified as "comparison” when it compares or contrasts the work in the cited paper to the author’s work. It overlaps with the first category when the citing sentence says one approach is not as good as the other approach. In this case we use the first category.

# Our approach permits an alternative to minimum error-rate training (MERT; Och, 2003);

# Use

# A citing sentence is classified as "use” when the citing paper uses the method, idea or tool of the cited paper.

# We perform the MERT training (Och, 2003) to tune the optimal feature weights on the development set.

# Substantiating

# A citing sentence is classified as “substantiating” when the results, claims of the citing work substantiate, verify the cited paper and support each other.

# It was found to produce automated scores, which strongly correlate with human judgements about translation fluency (Papineni et al. , 2002).

# Basis

# A citing sentence is classified as “basis” when the author uses the cited work as starting point or motivation and extends on the cited work.

# Our model is derived from the hidden-markov model for word alignment (Vogel et al., 1996; Och and Ney, 2000).

# Neutral (Other)

# A citing sentence is classified as “neutral” when it is a neutral description of the cited work or if it doesn’t come under any of the above categories.

# The solutions of these problems depend heavily on the quality of the word alignment (Och and Ney, 2000).

# Table 2: Annotation scheme for citation purpose. Motivated by the work of (Spiegel-Rösing, 1977) and (Teufel et al., 2006)
# """.strip()

# def label_citation_purpose(text):
#     response = openai.Completion.create(
#             engine="text-davinci-003",
#             prompt=f"Label the citation purpose of the following text in terms of 'Criticizing', 'Comparison', 'Use', 'Substantiating', 'Basis', and 'Neutral(Other)': \"{text}\" (Note: you should only choose one label for the text; FYI: \"{rules}\")"
#     )

#     label = response.choices[0].text.strip()

#     return label


# def update_jsonl_with_label(file_path, updated_data):
#     with open(file_path, 'w', encoding='utf-8') as file:
#         for data in updated_data:
#             line = json.dumps(data) + "\n"
#             file.write(line)

# def main():
#     args = get_args()
#     openai.api_key = args.api_key
#     file_path = args.file_path
#     updated_data = []
#     count = 0
#     # Read each entry, get the label from GPT, and append the label to the entry
#     for text, data in read_string_from_jsonl(file_path):
#         label = label_citation_purpose(text)
#         data["gpt_label"] = label
#         updated_data.append(data)
#         count += 1
#         if count == 50: break

#     # Update the jsonl file with the new data
#     update_jsonl_with_label(file_path, updated_data)

# if __name__ == "__main__":
#     main()
