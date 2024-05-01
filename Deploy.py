import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Tuple

from config.Configuration import Configuration, JFrog, PXEServerConfig
from deployment.Deployment import Deployment
from integration.Artifactory import Artifactory
from logger.Logger import init_logger
from utils.Utilities import run_command


class PxeDeployer(object):
    ARTIFACT_FOLDER_FORMAT: str = '%Y_%m_%d_%H_%M_%S'

    def __init__(self):
        self.config: Configuration = Configuration.get_configuration()
        self.logger: logging.Logger = init_logger()
        self.deployer: Deployment = Deployment()

        self.jfrog_config: JFrog = self.config.jfrog
        self.pxe_server_config: PXEServerConfig = self.config.pxe_server

        try:
            Path(self.pxe_server_config.artifacts_dir).mkdir(parents=True, exist_ok=True)
        except OSError as _:
            raise RuntimeError(f'Failed to create/access an Artifacts folder {self.pxe_server_config.artifacts_dir}')

        self.artifactory: Artifactory = Artifactory(host=self.jfrog_config.host,
                                                    username=self.jfrog_config.username,
                                                    password=self.jfrog_config.password)

    def get_latest_local_image(self,
                               artifacts_dir: Path) -> Tuple[datetime, Path]:
        path, most_recent = Path(), datetime(year=1, month=1, day=1)
        for entry in Path(artifacts_dir).iterdir():
            if entry.is_dir():
                folder_data: datetime = datetime.strptime(entry.name, self.ARTIFACT_FOLDER_FORMAT)
                if folder_data > most_recent:
                    most_recent = folder_data
                    path = entry.absolute()

        return most_recent, path

    def download_jfrog_file(self,
                            remote_path: str,
                            local_dst_path) -> bool:
        self.logger.debug(f'Downloading {remote_path} ---> {local_dst_path}')
        ok, msg = self.artifactory.download_artifact(f'{remote_path}', f'{local_dst_path}')
        if not ok:
            self.logger.error(f'Download failed: {msg}')
            return False

        self.logger.debug(f'OK. {os.path.getsize(local_dst_path)} bytes downloaded')
        return True

    def download_artifacts(self,
                           latest_build_date: datetime,
                           remote_build_folder: str) -> bool:
        folder_name: str = latest_build_date.strftime(self.ARTIFACT_FOLDER_FORMAT)
        folder_path: str = f'{self.pxe_server_config.artifacts_dir}/{folder_name}'

        changes_file, image_file_name = 'ChangeSet.txt', Artifactory.IMAGE_FILE_NAME
        Path(folder_path).mkdir(parents=True, exist_ok=False)

        if not self.download_jfrog_file(f'{remote_build_folder}/{changes_file}',
                                        f'{folder_path}/{changes_file}'):
            return False
        if not self.download_jfrog_file(f'{remote_build_folder}/{image_file_name}',
                                        f'{folder_path}/{image_file_name}'):
            return False

        cmd: str = f'ln -fs {folder_path}/{image_file_name} {self.pxe_server_config.sdcard_image_path}'
        _, err_code = run_command(cmd, print_output=False)

        return True

    def download_latest_image(self) -> bool:

        # Latest/most recent downloaded SDCard image (stored locally in the 'config.pxe_server.artifacts_dir' folder):
        local_date, _ = self.get_latest_local_image(Path(self.pxe_server_config.artifacts_dir))

        artifactory: Artifactory = Artifactory(host=self.jfrog_config.host,
                                               username=self.jfrog_config.username,
                                               password=self.jfrog_config.password)
        latest_build_date, build_folder_path = artifactory.get_latest_build()

        self.logger.debug(f'Latest JFrog image is : {latest_build_date}. Latest deployed: {local_date}')
        if local_date >= latest_build_date:
            self.logger.debug(f'Already have an latest image build: "{local_date}" in {self.pxe_server_config.artifacts_dir}')
            return True

        if not self.download_artifacts(latest_build_date, build_folder_path):
            self.logger.error("Failed to download some artifacts")
            return False

        return True

    def deploy_nodes(self) -> bool:
        return self.deployer.deploy(nodes=self.config.csl_nodes)


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--download', help="Try to download the latest sdcard image from JFrog Artifactory",
                        action='store_true')
    params = parser.parse_args()

    pxe_deployer: PxeDeployer = PxeDeployer()
    if params.download and not pxe_deployer.download_latest_image():
        sys.stderr.write("Failed to download a latest sdcard image from JFrog")
        sys.exit(0)

    pxe_deployer.deploy_nodes()
