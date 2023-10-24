import argparse
import urllib.parse
import urllib.request


class ArgParser:
    @staticmethod
    def get_arguments() -> argparse.Namespace:
        args = ArgParser._parse_arguments()
        return args

    @staticmethod
    def _parse_arguments() -> argparse.Namespace:
        parser = argparse.ArgumentParser()
        parser.add_argument("name", help="url of the notion.so page to scrape", metavar="RESEARCHER_NAME")
        return parser.parse_args()

ARGS = ArgParser.get_arguments()
