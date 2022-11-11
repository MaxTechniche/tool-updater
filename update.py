#!/usr/bin/env python3

"""
TODO:

"""

import sys
import argparse
import os
import errno
import shutil
import requests
import filetype
from urllib.error import HTTPError, URLError
import urllib.request

import ssl

ssl._create_default_https_context = ssl._create_unverified_context

from urllib.request import Request, urlopen
from bs4 import BeautifulSoup
import yaml
import lxml
import re
from datetime import datetime

parser = argparse.ArgumentParser(description="Update tools")
parser.add_argument("-f", type=str, default="toollist.yml", required=False, dest="file")
parser.add_argument(
    "-b", type=str, default="toollist_backup.yml", required=False, dest="backup"
)
parser.add_argument(
    "--verify",
    default=False,
    required=False,
    help="verify that the latest version is downloaded",
    dest="verify",
    action="store_true",
)
parser.add_argument(
    "--skip-remove",
    default=False,
    required=False,
    help="remove tools from update list that have errors",
    dest="skip_remove",
    action="store_true",
)
path = sys.argv[0]


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


class DownloadTooLargeError(Error):
    """The file download is too large"""

    pass


class RemoteDownloadError(Error):
    """Download is not available on Filehorse.com"""

    pass


class Tool:
    def __init__(self, **kwargs):
        self.link = kwargs.get("link")
        self.soup = self.connect_to_link()

        self.latest_version = kwargs.get("latest version") or 0

        self.type = self.get_tool_type()
        self.size = self.get_file_size()
        self.status = self.get_tool_security_status()
        self.windows_versions = self.get_windows_versions()
        self.website = self.get_product_website()
        self.downloaded = kwargs.get("downloaded")
        self.rating = self.get_rating()
        self.file_type = self.get_file_type()
        self.error = kwargs.get("error")

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

    def get_info(self, update=True):
        return {
            "latest version": self.latest_version,
            "downloaded": self.downloaded
            if (update and self.downloaded)
            else datetime.today().strftime("%B %d, %Y"),
            "link": self.link,
            "windows versions": self.windows_versions,
            "status": self.status,
            "rating": self.rating,
            "size": self.size,
            "type": self.type,
            "website": self.website,
            "error": self.error,
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

        # print(version, self.latest_version)
        # print(version > str(self.latest_version))
        if version and (version > str(self.latest_version)):
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
            self.latest_version = version
            self.download(version)
        else:
            if parser.parse_args().verify:
                print("verifying download")
                self.download(version)
        print("Up to date")

    def download(self, version):
        download_soup = BeautifulSoup(
            requests.get(self.link + "download/").text, "lxml"
        )
        download_url = download_soup.find(rel="nofollow noopener").get("href")

        download_style = download_soup.find("div", class_="dl-right")

        if "external website" in download_style.text:
            raise RemoteDownloadError

        path = f"./tools/{self.name}"
        filename = f"{self.name} {version}"
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
        print("Version not found on system, downloading...")

        req = Request(
            download_url,
            headers={"User-Agent": "Mozilla/5.0"},
        )

        try:
            webpage = urlopen(req)
            webpage = webpage.read()
        except OverflowError:
            raise DownloadTooLargeError

        with open(filepath, "wb") as f:
            f.write(webpage)

        # with requests.get(
        #     download_url, stream=True, headers={"User-Agent": "Mozilla/5.0"}
        # ) as r:
        #     with open(filepath, "wb") as f:
        #         shutil.copyfileobj(r.raw, f)

        kind = filetype.guess(filepath)

        if kind:
            os.rename(filepath, filepath + "." + kind.extension.lower())
        else:
            os.rename(filepath, filepath + ".exe")
        print(f"{self.name} version {self.latest_version} was successfully downloaded.")

    def __repr__(self):
        s = (
            self.name
            + "\nVersion:"
            + self.latest_version
            + "\nDownloaded:"
            + self.downloaded
        )
        return s


def dump_yaml(file, data):
    with open(file, "w") as f:
        f.write(yaml.safe_dump(data))


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


def sort_tools(file):
    dump_yaml(file, load_yaml(file))


def main():

    url = "https://www.filehorse.com/"
    check_connection_to_filehorse(url)

    errors = []
    path = os.path.split(sys.argv[0])[0]
    if not path:
        path = os.getcwd()
    print("Path:", path)
    file = parser.parse_args().file
    file_path = os.path.join(path, file)
    print("File:", file)
    print("File_path:", file_path)
    backup = parser.parse_args().backup
    backup_path = os.path.join(path, backup)
    print("Backup:", backup)
    print("Backup_path:", backup_path)
    print()

    if file not in os.listdir(path):
        print("No toollist found in current directory")
        with open(file_path, "w") as f:
            f.write("none:")

    if backup not in os.listdir(path):
        print("No backup found in current directory")
        with open(backup_path, "w") as f:
            f.write("none:")

    def run():
        sort_tools(file_path)
        tools = load_yaml(file_path)
        for name, info in tools.items():
            print("-----------------------------------------")
            print(f"Checking {name}...")
            if not info:
                dump_yaml(file_path, tools)
                continue

            try:
                tool = Tool(**info)
                tool.name = name
            except ConnectionError as ce:
                print("Possible Broken Link")
                print("Unable to continue!")
                tool.error = "Unknown link error: %s" % ce
                errors.append(tool)
                dump_yaml(file_path, tools)
                continue

            try:
                tool.check_for_update()
            except (VersionExistsError, FileExistsError):
                print("Version appears to already be downloaded.")
                tools[name] = tool.get_info(update=False)

                dump_yaml(file_path, tools)
                continue
            except DisabledError:
                print("New version found, but download is disabled")
                tool.error = "Download is disabled"
                errors.append(tool)
            except DownloadTooLargeError:
                print("File is too large to download.")
                tool.error = "Too large to download"
                errors.append(tool)
                tools[name] = tool.get_info(update=False)
            except RemoteDownloadError:
                print("Tool is not available directly from Filehorse.")
                tool.error = "Download not available directly from Filehorse"
                errors.append(tool)
                tools[name] = tool.get_info(update=False)

            except (HTTPError, URLError) as e:
                print("Unknown connection error occured")
                print(e)
                tool.error = "Unknown error: %s" % e
                errors.append(tool)
                tools[name] = tool.get_info(update=False)

                dump_yaml(file_path, tools)
                continue

            tools[name] = tool.get_info()
            dump_yaml(file_path, tools)

    try:
        run()
    except AttributeError as e:
        print(e)
        shutil.copyfile(backup_path, file_path)
        # os.system("copy toollist_backup.yml toollist.yml")
        try:
            run()
        except AttributeError:
            print("No tools detected.")

    shutil.copyfile(file_path, backup_path)
    # os.system("copy toollist.yml toollist_backup.yml")

    if errors:
        print("Errors:")
        print(*[(tool.name, tool.error) for tool in errors], sep="\n")

        if not parser.parse_args().skip_remove:
            delete = (
                input(
                    "Would you like to remove any of these programs from the tool list?: y/[n]"
                )
                or "n"
            )
            if delete.lower() == "y":
                tools = load_yaml(file_path)
                for tool in errors:
                    delete = (
                        input(f"Would you like to remove {tool.name}? y/[n]: ").lower()
                        or "n"
                    )
                    if delete.lower() == "y":
                        deleted_tool = tools.pop(tool.name)
                        print(f"Removed {tool.name} from tool list.")
                        print()
                dump_yaml(file_path, tools)
                shutil.copyfile(file_path, backup_path)
                # os.system("copy toollist.yml toollist_backup.yml")


if __name__ == "__main__":
    main()
    print()
    print("Updater complete")
