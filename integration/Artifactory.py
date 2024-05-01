import datetime
import requests
import urllib.parse

from requests import Response
from http import HTTPStatus
from typing import List, Dict, Tuple


class Artifactory(object):

    SECURE_COMMUNICATION_REPO: str = 'secure-communication'
    ARCH_FLAVOR: str = 'cm4io_nfs'
    IMAGE_FILE_NAME: str = 'sdcard.img'
    UPDATED_ATTR_FORMAT: str = '%Y-%m-%dT%H:%M:%S'

    def __init__(self,
                 host: str, username: str, password: str):
        # TODO: Replace (host/username/password) with some Credentials class
        self.host: str = host
        self.username: str = username
        self.password: str = password
        self.api_url: str = f'{self.host}/api/search/aql'

        find_params: Dict = {'repo': self.SECURE_COMMUNICATION_REPO,
                             'path': {'$match': f"*{self.ARCH_FLAVOR}*"},
                             'name': f"{self.IMAGE_FILE_NAME}"}
        sort_params: Dict = {'$desc': ['updated']}

        self.last_image_query: str = (
            f'items.find({find_params}).sort({sort_params}).limit(1)'.replace('\'', '\"'))

    def get_latest_build(self) -> Tuple[datetime.datetime, str]:
        with requests.Session() as session:
            session.auth = (self.username, self.password)
            print(self.api_url,)
            response: Response = session.post(self.api_url, data=self.last_image_query)
            if HTTPStatus.OK != response.status_code:
                raise RuntimeError('Failed to find files matching pattern')

            results: List = response.json()['results']
            if not results:
                raise RuntimeError(f'Empty results: {response.json()}')

            artifact: Dict = results[0]

            date_str_no_mills: str = artifact['updated'].split('.')[0]
            date = datetime.datetime.strptime(date_str_no_mills, self.UPDATED_ATTR_FORMAT)

            return date, artifact['path']

    def download_artifact(self,
                          artifact_path: str,
                          destination_file: str) -> Tuple[bool, str]:
        with requests.Session() as session:
            session.auth = (self.username, self.password)
            file_url: str = f'{self.host}/{self.SECURE_COMMUNICATION_REPO}/{urllib.parse.quote(artifact_path)}'
            response: Response = session.get(file_url, stream=True)
            if HTTPStatus.OK != response.status_code:
                return False, f'Failed to get the artifact file: {file_url}'

            with open(destination_file, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)

            return True, 'OK'

    def download_artifact_by_hash(self,
                                  repo_name: str,
                                  commit_hash: str,
                                  file_name: str,
                                  destination_file: str) -> Tuple[bool, str]:
        with requests.Session() as session:
            session.auth = (self.username, self.password)

            api_pattern_query: str = ('items.find({"repo":"' + repo_name + '", "path":{"$match":"*' + self.ARCH_FLAVOR +
                                      '*' + commit_hash + '*"}, "name": "' + file_name + '"})')
            response: Response = session.post(self.api_url, data=api_pattern_query)
            if HTTPStatus.OK != response.status_code:  # HTTP_OK
                return False, (f'Failed to find files matching pattern: '
                               f'[repo: {repo_name}, path: *{commit_hash}, name: {file_name}]')

            results: List = response.json()['results']
            if not results:
                return False, f'Empty result: {response.json()}'

            artifact: Dict = dict(results[0])
            path = artifact['path'] + "/" + artifact['name']

            file_url: str = f'{self.host}/{repo_name}/{urllib.parse.quote(path)}'

            response = session.get(file_url, stream=True)
            if HTTPStatus.OK != response.status_code:  # HTTP_OK
                return False, f'Failed to get the artifact file: {file_url}'

            with open(destination_file, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)

            return True, 'OK'

    def download_image_by_hash(self,
                               commit_hash: str,
                               destination_file: str) -> Tuple[bool, str]:
        return self.download_artifact_by_hash(repo_name=self.SECURE_COMMUNICATION_REPO,
                                              file_name=self.IMAGE_FILE_NAME,
                                              commit_hash=commit_hash,
                                              destination_file=destination_file)

    # TODO:
    #  1. Wait for artifact ??
    #  2. Subscribe to updated ?? (if new artifact appears)
