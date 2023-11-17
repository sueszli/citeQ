import logging
import traceback
import functools
from rich.logging import RichHandler
import os

BANNER_ASCII = """
\u001b[32m
            88                        ,ad8888ba,
            ""    ,d                 d8"'    `"8b
                  88                d8'        `8b
 ,adPPYba,  88  MM88MMM  ,adPPYba,  88          88
a8"     ""  88    88    a8P_____88  88          88
8b          88    88    8PP\"\"\"\"\"\"\"  Y8,    "88,,8P
"8a,   ,aa  88    88,   "8b,   ,aa   Y8a.    Y88P
 `"Ybbd8"'  88    "Y888  `"Ybbd8"'    `"Y8888Y"Y8a

🎓 citation sentiment classifier
\u001b[0m
"""
HIGHLIGHTED_WORDS = [""]
IGNORED_STACK_FRAMES = 8


class LogWrapper(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        # add indentation based on stack depth
        tab_char = " " * 3
        indentation_level = len(traceback.extract_stack()) - IGNORED_STACK_FRAMES
        return f"{tab_char * indentation_level}{msg}", kwargs


class LogInitializer:
    @staticmethod
    def get_log() -> logging.LoggerAdapter:
        # see: https://rich.readthedocs.io/en/stable/reference/logging.html
        rich_handler = RichHandler(rich_tracebacks=True, show_time=False, show_path=False, keywords=HIGHLIGHTED_WORDS)
        logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[rich_handler])

        os.system("cls" if os.name == "nt" else "clear")
        print(BANNER_ASCII)
        return LogWrapper(logging.getLogger("scrape-logger"), {})


LOG_SINGLETON = LogInitializer.get_log()


def trace(print_args: bool = True):
    def decorator(func):
        # see: https://realpython.com/primer-on-python-decorators/#debugging-code
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            input_string = "⮕ "
            input_string += func.__name__ + "("
            if print_args:
                input_string += ", ".join([str(arg) for arg in args])
            input_string += ")"
            LOG_SINGLETON.info(input_string)

            result = func(*args, **kwargs)

            output_string = result if result is not None else ""
            LOG_SINGLETON.info(f"⬅ {output_string if print_args else ''}")
            return result

        return wrapper

    return decorator
