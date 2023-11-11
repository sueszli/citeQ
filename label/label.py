import json
import argparse
import os
import openai
import time


def get_args():
    parser = argparse.ArgumentParser(description="Process args")
    parser.add_argument("api_key", type=str, help="OpenAI API key")
    parser.add_argument("file_path", type=str, help="Path to the JSONL file to process")
    return parser.parse_args()


def read_string_from_jsonl(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        for line in file:
            data = json.loads(line)
            yield data["string"], data


def label_citation_purpose(text):
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=f"Label the citation purpose of the following text in terms of 'Criticizing', 'Comparison', 'Use', 'Substantiating', 'Basis', and 'Neutral(Other)': \"{text}\" (Note: you should only choose one label for the text)",
    )

    label = response.choices[0].text.strip()

    return label


def update_jsonl_with_label(file_path, updated_data):
    with open(file_path, "w", encoding="utf-8") as file:
        for data in updated_data:
            line = json.dumps(data) + "\n"
            file.write(line)


def main():
    args = get_args()
    openai.api_key = args.api_key
    file_path = args.file_path
    updated_data = []

    # Read each entry, get the label from GPT, and append the label to the entry
    for text, data in read_string_from_jsonl(file_path):
        label = label_citation_purpose(text)
        data["gpt_label"] = label
        updated_data.append(data)

    # Update the jsonl file with the new data
    update_jsonl_with_label(file_path, updated_data)


if __name__ == "__main__":
    main()
