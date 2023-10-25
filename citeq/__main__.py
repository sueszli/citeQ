import asyncio
import aiohttp
from aiohttp import ClientSession, ClientConnectorError

import pathlib
import sys


import argparse
from logger import LOG_SINGLETON as LOG, trace


# async def fetch_html(url: str, session: ClientSession) -> tuple:
#     try:
#         resp = await session.request(method="GET", url=url)
#     except ClientConnectorError:
#         return (url, 404)
#     return (url, resp.status)


# async def make_requests(urls: set) -> None:
#     async with ClientSession() as session:
#         tasks = []
#         for url in urls:
#             tasks.append(fetch_html(url=url, session=session))
#         results = await asyncio.gather(*tasks)

#     for result in results:
#         print(f"{result[1]} - {str(result[0])}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CiteQ: a citation analysis tool")
    parser.add_argument("name", nargs="+", help="the researchers name", type=str)
    parser.add_argument("university", nargs="?", help="the researchers university", type=str)
    parser.add_argument("field", nargs="?", help="the researchers field of study", type=str)

    args = parser.parse_args()
    name_str = " ".join(args.name).strip().lower()

    # asyncio.run(make_requests(urls=urls))
