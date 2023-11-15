from unstructured.partition.pdf import partition_pdf
from nltk.tokenize import sent_tokenize
import re


class RegexCitationExtractor:
    @staticmethod
    def read_file(file_path):
        return partition_pdf(file_path, url=None)

    @staticmethod
    def find_bibliography(file):
        # find the bibliography section
        for i, element in enumerate(file):
            if element.category == "Title":
                if "REFERENCES" in element.text:
                    return i

        for i, element in enumerate(file):
            if "REFERENCES" in element.text:
                return i

        raise Exception("No bibliography found")

    @staticmethod
    def extract_references(file):
        bib_start = RegexCitationExtractor.find_bibliography(file)

        # extract the references
        references = {}
        keys = []
        reference_regex = re.compile(r"\[\d+\]")
        no_match_count = 0
        double_entry = False
        for i, element in enumerate(file[bib_start:]):
            if no_match_count > 3 or double_entry:
                break

            # find all the matches
            matches = reference_regex.findall(element.text)

            for j, match in enumerate(matches):
                # extract the refenrece number
                ref_num = int(match[1:-1])

                if ref_num in references:
                    double_entry = True
                    break

                # get the refenrece text
                start = element.text.find(match) + len(match)
                if i > 0 and (start > 2 + len(match)) and j == 0:
                    references[keys[-1]]["ref"] += element.text[:start]

                if j < len(matches) - 1:
                    end = element.text.find(matches[j + 1])
                else:
                    end = len(element.text)
                ref_text = element.text[start:end]
                keys.append(ref_num)
                references[ref_num] = {"idx": ref_num, "ref": ref_text, "citation": []}

            if len(matches) == 0:
                no_match_count += 1
                references[keys[-1]]["ref"] += element.text
            else:
                no_match_count = 0

        return references

    @staticmethod
    def extract_citations(file):
        references = RegexCitationExtractor.extract_references(file)
        bib_start = RegexCitationExtractor.find_bibliography(file)

        # extract the citations
        citations = []
        citation_regex = re.compile(r"\[\d+(?:,\s*\d+)*\]")

        # concatanate the text before the bibliography
        body_text = ""
        for element in file[:bib_start]:
            body_text += element.text + " "

        # tokenize the text into sentences
        sentences = sent_tokenize(body_text)

        # find the sentences with the citations
        for sentence in sentences:
            # find all the matches
            matches = citation_regex.findall(sentence)

            for match in matches:
                # extract the refenrece number
                ref_nums = [int(num) for num in match[1:-1].split(",")]
                citations.append({"idx": ref_nums, "ref": sentence})

        # combine the citations with the references
        for citation in citations:
            for ref_num in citation["idx"]:
                references[ref_num]["citation"].append(citation["ref"])

        return references
