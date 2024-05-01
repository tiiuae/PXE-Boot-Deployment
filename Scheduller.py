import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Tuple

from config.Configuration import Configuration, JFrog, PXEServerConfig, RobotConfig
from deployment.Deployment import Deployment
from integration.Artifactory import Artifactory
from logger.Logger import init_logger
from utils.Utilities import run_command


class Scheduler(object):
    POLL_REPEAT_TIMEOUT: float = 5.0 * 1

    ARTIFACT_FOLDER_FORMAT: str = '%Y_%m_%d_%H_%M_%S'

    def __init__(self):
        self.config: Configuration = Configuration.get_configuration()
        self.logger: logging.Logger = init_logger()
        self.deployer: Deployment = Deployment()

        self.jfrog_config: JFrog = self.config.jfrog
        self.pxe_server_config: PXEServerConfig = self.config.pxe_server
        self.robot_config: RobotConfig = self.config.robot

        try:
            Path(self.pxe_server_config.artifacts_dir).mkdir(parents=True, exist_ok=True)
        except OSError as _:
            raise RuntimeError(f'Failed to create/access an Artifacts folder {self.pxe_server_config.artifacts_dir}')

        self.artifactory: Artifactory = Artifactory(host=self.jfrog_config.host,
                                                    username=self.jfrog_config.username,
                                                    password=self.jfrog_config.password)

    def get_latest_local_image(self) -> Tuple[datetime, Path]:
        path, most_recent = Path(), datetime(year=1, month=1, day=1)
        for entry in Path(self.pxe_server_config.artifacts_dir).iterdir():
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

    def validate_configuration(self) -> bool:
        start_up_info: str = '\n' + '--' * 100
        start_up_info += f'\n\tStartup time       : {datetime.now()}'
        start_up_info += f'\n\tWorking directory  : {self.pxe_server_config.working_dir}'
        start_up_info += f'\n\tImages folder      : {self.pxe_server_config.artifacts_dir}'
        start_up_info += f'\n\tJFrog Host address : {self.jfrog_config.host}'
        start_up_info += f'\n\tMikrotik host      : {self.config.router.host}'
        start_up_info += '\n' + '--' * 100
        self.logger.debug(start_up_info)

        return True

    def deploy_nodes(self) -> bool:
        return self.deployer.deploy(nodes=self.config.csl_nodes)

    def deploy_and_test(self) -> bool:
        if not self.deploy_nodes():
            self.logger.error(f'Failed to deploy configuration')
            return False

        return self.run_tests()

    def run_tests(self) -> bool:
        self.logger.debug('\n' + '==' * 80 + '\n' + '\t' * 7 + 'Running RobotFramework tests' + '\n' + '==' * 80)

        for test_name in self.robot_config.get_tests():
            cmd: str = f'robot -d {self.robot_config.reports_dir} {self.robot_config.tests_dir}/{test_name}'
            message, err_code = run_command(cmd)
            self.logger.debug('\n\n' + message + '\n')

        return True

    def start(self):
        if not self.validate_configuration():
            return

        local_date, _ = self.get_latest_local_image()
        while True:
            latest_build_date, build_folder_path = self.artifactory.get_latest_build()
            self.logger.debug(f'Latest JFrog image is : {latest_build_date}. Latest deployed: {local_date}')
            if latest_build_date > local_date:
                if not self.download_artifacts(latest_build_date, build_folder_path):
                    # TODO: How to handle ??? Email / Slack notification ???
                    self.logger.error("Failed to download some artifacts")
                local_date = latest_build_date
                self.deploy_and_test()
            else:
                self.logger.debug('No need to update (^_^)')
                time.sleep(self.POLL_REPEAT_TIMEOUT)


if __name__ == '__main__':
    scheduler = Scheduler()
    scheduler.start()
