#!/usr/bin/env python3

"""
TODO: 

"""

import os
import re
import sys
import requests
import argparse
from bs4 import BeautifulSoup
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

FILEHORSE_SEARCH = "https://www.filehorse.com/search?q="

parser = argparse.ArgumentParser(description="Update tools")
parser.add_argument("-f", type=str, default="toollist.yml", required=False, dest="file")


def query():
    search_query = input("Search: ")
    return search_query


def search_filehorse(user_query):
    url = FILEHORSE_SEARCH + user_query
    soup = BeautifulSoup(requests.get(url).text, "lxml")
    return soup.find("ul", class_="software_list").find_all(
        "div", class_="short_description"
    )


def get_tool_info(tool):
    print("Getting tool info...")

    name = tool.h3.a.text
    desc = tool.find("div", class_="description_hide").text
    link = tool.find("div", class_="cat_dl_btn").a.attrs["href"]
    print("Name:", name)
    print("Desc:", desc)

    try:
        print("Size:", re.search("\d+\.?\d+\s*(M|K|G)B", tool.p.text).group())
    except AttributeError:
        pass
    print()

    return {"name": name, "desc": desc, "link": link}


def add_tool_to_tool_list(tool, file_path):
    print("Adding tool to tool list...")

    nav = next(
        BeautifulSoup(requests.get(tool["link"]).text, "lxml")
        .find(itemprop="softwareVersion")
        .children
    )

    version = re.search(" R?(\d+\s*\.?((B|b)uild)?\s*)+", nav)

    if version:
        name = re.sub("\s+", " ", nav.replace(version.group(), "").strip())
    else:
        name = tool["name"]

    try:
        with open(file_path, "a") as f:
            f.write("%s: {link: %s}\n" % (name, tool["link"]))
        print(f"{name} added to tool list.")
    except Exception as e:
        print(e)
    print()


def download(tool):
    print(f"Atempting to download tool")
    print()


def ask_user_if_update():
    update = input(
        "Would you like to update your tool list right now? [y]/n:",
        end=" ",
    )
    if update == "y":
        return True
    return False


# TODO: Tell the user to adjust their search if the results were not satisfactory.


def main():

    path = os.path.split(sys.argv[0])[0]
    file = parser.parse_args().file
    file_path = os.path.join(path, file)

    added_tools = []
    # query until no input
    querying = True
    while querying:
        user_query = query().strip()
        if not user_query:
            querying = False
            break

        results = search_filehorse(user_query)
        if not results:
            print(f"No results found for search {user_query}")
            continue

        for tool in results:
            print("------------------------")
            print("Tool found")
            tool = get_tool_info(tool)

            if (
                input("Would you like to add this tool to your tool list? [y]/n: ")
                or "y"
            ) == "y":
                added_tools.append(tool["name"])
                add_tool_to_tool_list(tool, file_path)

            # elif (
            #     input("Would you like to download this tool just one time? [y]/n: ")
            #     or "y"
            # ) == "y":
            #     download(tool)

    update_ = (
        input(
            "Would you like to check for updates on your tool list right now? [y]/n: "
        ).lower()
        or "y"
    )
    if update_ == "y":
        os.system("python update.py")


if __name__ == "__main__":
    main()
