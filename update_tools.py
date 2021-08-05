#!/usr/bin/env python3

"""
TODO: Check if generic file for updated version exists before downloading

"""

import os
import errno
import requests
import filetype
from urllib.error import HTTPError
import urllib.request
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup
import yaml
import lxml
import re
from datetime import datetime


class Error(Exception):
    """Base error class"""

    pass


class ConnectionError(Error):
    """Error connecting to the file"""

    pass


class InformationError(Error):
    """Unable to gather information"""

    pass


class UnknownError(Error):
    """Other errors of unknown origin"""

    pass


class FileNotFoundError(Error):
    """File was erased or lost"""

    pass


class DisabledError(Error):
    """File download is disabled because of security status"""

    pass


class VersionExistsError(Error):
    """The files version currently exists on the computer"""

    pass


class Tool:
    def __init__(self, **kwargs):
        self.link = kwargs.get("link")
        self.soup = self.connect_to_link()

        self.name = kwargs.get("name")
        self.version = kwargs.get("version") or 0

        self.type = self.get_tool_type()
        self.size = self.get_file_size()
        self.status = self.get_tool_security_status()
        self.windows_versions = self.get_windows_versions()
        self.website = self.get_product_website()
        self.updated = kwargs.get("updated")
        self.rating = self.get_rating()
        self.file_type = self.get_file_type()

    def connect_to_link(self):
        """Connect to the link and get page html."""
        if self.link:
            try:
                return BeautifulSoup(requests.get(self.link).text, "lxml")
            except requests.exceptions.ConnectionError as e:
                raise ConnectionError(e)

    def get_below_name(self):
        return self.soup.find(class_="program-below-name-container").text

    def get_tool_type(self):
        try:
            types = ["Freeware", "Trial", "Open Source", "Demo", "Paid", "Free to Play"]
            name_container = self.get_below_name()
            for t in types:
                if t in name_container:
                    return t
        except Exception as e:
            raise ConnectionError

    def get_file_size(self):
        try:
            return re.search("\d+\.?\d+\s*(M|K|G)B", self.get_below_name()).group()
        except Exception as e:
            raise ConnectionError

    def get_tool_security_status(self):
        statuses = {
            "gray": "Disabled",
            "red": "Warning",
            "orange": "Suspicious",
            "green": "Clean",
        }
        try:
            status = self.soup.find(class_="below-download-link").p.get("class")[0]
            return statuses[status]
        except KeyError:
            return
        except Exception as e:
            raise ConnectionError

    def get_windows_versions(self):
        try:
            versions = self.soup.find(itemprop="operatingSystem").text
            versions = re.sub("(W|w)indows ?", "", versions)
            versions = re.sub(" ?64", " (64-bit)", versions)
            return versions
        except Exception as e:
            raise ConnectionError

    def get_product_website(self):
        try:
            return self.soup.find(itemprop="publisher").select("p > a")[1].get("href")
        except Exception as e:
            raise ConnectionError

    def get_rating(self):
        try:
            return float(self.soup.find(itemprop="ratingValue")["content"])
        except Exception as e:
            raise ConnectionError

    def get_file_type(self):
        pass

    def get_info(self):
        return {
            "name": self.name,
            "version": self.version,
            "updated": datetime.today().strftime("%B %d, %Y"),
            "link": self.link,
            "windows versions": self.windows_versions,
            "status": self.status,
            "rating": self.rating,
            "size": self.size,
            "type": self.type,
            "website": self.website,
        }

    def check_for_update(self):
        """Checks the current tool to see if there's an update."""

        nav = next(self.soup.find(itemprop="softwareVersion").children)

        text_version = re.search(" R?(\d+\s*\.?((B|b)uild)?\s*)+", nav)

        version = None
        if text_version:
            text_version = text_version.group()
            version = re.sub("(B|b)uild", ".", text_version)
            version = str(re.sub("\s+", "", version))

        self.name = re.sub("\s+", " ", nav.replace(text_version or "", "").strip())

        if version and (version > str(self.version)):
            if self.status == "Disabled":
                raise DisabledError

            print("New Version found. Attempting download of", end=" ")

            type_text = self.soup.find(class_="program-below-name-container").text
            size = re.search("\d+\.\d+ (M|K|G)B", type_text)
            if size:
                size = size.group()
                print(size)
            else:
                print(self.name)

            self.version = version
            self.download()
            print(f"{self.name} version {self.version} was successfully downloaded.")
        else:
            print("Up to date.")

    def download(self):
        download_soup = BeautifulSoup(
            requests.get(self.link + "download/").text, "lxml"
        )
        download_url = download_soup.find(rel="nofollow noopener").get("href")

        path = f"./tools/{self.name}"
        filename = f"{self.name} {self.version}"
        filepath = f"{path}/{filename}"
        if not os.path.exists(os.path.dirname(filepath)):
            try:
                os.makedirs(os.path.dirname(filepath))
            except OSError as exc:  # Guard against race condition
                if exc.errno != errno.EEXIST:
                    raise

        print("Checking to see if version already exists on system.")
        files = os.listdir(path)
        for file in files:
            if os.path.splitext(file)[0] == filename:
                raise VersionExistsError

        req = Request(
            download_url,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        webpage = urlopen(req).read()
        with open(filepath, "wb") as f:
            f.write(webpage)

        kind = filetype.guess(filepath)

        if kind:
            os.rename(filepath, filepath + "." + kind.extension.lower())
        else:
            os.rename(filepath, filepath + ".exe")

    def __repr__(self):
        s = self.name + "\nVersion:" + self.version + "\nUpdated:" + self.updated
        return s


def dump_yaml(file, data):
    with open(file, "w") as f:
        f.write(yaml.dump(data, Dumper=yaml.Dumper, default_flow_style=False))


def load_yaml(file):
    return yaml.load(
        open(file),
        Loader=yaml.Loader,
    )


def check_connection_to_filehorse(url):
    print()
    print(f"Checking connection to {url}")
    print("Please wait...")

    # time.sleep(1)

    response = requests.get(url)

    if response.status_code != 200:
        print("Unsuccessful connection!")
        print(f"Status code {response.status_code} from {url}")
        exit(1)

    print("Connection Successful")
    print("Starting Updater...")
    print()
    return response


def main():

    url = "https://www.filehorse.com/"
    check_connection_to_filehorse(url)

    errors = ["Errors:"]

    file = "./tools_info.yml"

    def run():
        tools = load_yaml(file)
        for name, info in tools.items():
            print("-----------------------------------------")
            print(f"Checking {name}...")
            if not info:
                dump_yaml(file, tools)
                continue

            try:
                tool = Tool(**info)
                tool.name = name
            except ConnectionError as ce:
                print("Possible Broken Link")
                print("Unable to continue!")
                tools[name]["ERROR"] = "Broken or mistyped link"
                dump_yaml(file, tools)
                continue

            try:
                tool.check_for_update()
            except FileExistsError:
                print("Version appears to already be downloaded.")
            except DisabledError:
                print("New version found, but download is disabled")
                errors.append(f"{name} is disabled")
            except VersionExistsError:
                print("Version appears to already be downloaded.")
            except HTTPError as e:
                print("Unknown connection error occured")
                print(e)
                errors.append(f"{name} had an unknown HTTPError")

            tools[name] = tool.get_info()

            dump_yaml(file, tools)

    try:
        run()
    except AttributeError:
        print("File info lost durring previous run, using backup")
        os.system("copy tools_info_backup.yml tools_info.yml")
        run()

    os.system("copy tools_info.yml tools_info_backup.yml")

    print(*errors, sep="\n")


if __name__ == "__main__":
    main()
    print()
    print("Updater complete")


# General Computer Shortcuts
# Ninite Website
# CrucialScan
# DupeGuru
# Frafs (Fraps) Bench Viewer
# Hirens BootCD
# LookInMyPC
# MaxxMEM2
# PerfMonitor2
# PowerMAX
# Procmon
# Winaero
# DoubleKiller
# Geek Uninstaller
# Hijack Hunter
# phoronix test suite
# Tech Tool Store
# TrID - File Identifier
# Ventoy
