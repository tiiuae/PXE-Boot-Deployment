from __future__ import annotations

import configparser
import os

from dataclasses import dataclass
from typing import List
from common.CSLNode import CSLNode


@dataclass
class Router(object):
    type: str
    host: str
    username: str
    password: str


@dataclass
class JFrog(object):
    host: str
    username: str
    password: str


@dataclass
class PXEServerConfig(object):
    ip_address: str
    filesystem_root: str
    working_dir: str
    sdcard_image_path: str
    artifacts_dir: str
    logs_dir: str


@dataclass
class RobotConfig(object):
    tests_dir: str
    reports_dir: str
    tests: List[str]

    def get_tests(self) -> List[str]:
        return [test.strip() for test in str(self.tests).split(',')]


class Configuration(object):
    __instance__: Configuration = None
    __initialized__: bool = False

    def __new__(cls, *args, **kwargs) -> Configuration:
        if cls.__instance__ is None:
            cls.__instance__ = super(Configuration, cls).__new__(cls)
        return cls.__instance__

    def __init__(self):
        if self.__initialized__:
            return
        self.__initialized__ = True

        self.config_dir: str = os.path.dirname(os.path.realpath(__file__))
        self.router: Router = None
        self.jfrog: JFrog = None
        self.robot: RobotConfig = None
        self.pxe_server: PXEServerConfig = None
        self.csl_nodes: List[CSLNode] = []

    def __parse_configuration(self):
        config = configparser.ConfigParser()

        # TODO: Filename to const?? or/and as input parameter ?
        config_file_path: str = f'{self.config_dir}/default.conf'
        if not config.read(config_file_path):
            raise RuntimeError(f'Failed to read configuration file {config_file_path}')

        router_section: configparser.SectionProxy = config['router']
        self.router = Router(type=router_section.get('type', None),
                             host=router_section.get('host', None),
                             username=router_section.get('username', None),
                             password=router_section.get('password', None))

        jfrog_section: configparser.SectionProxy = config['jfrog']
        self.jfrog = JFrog(host=jfrog_section.get('host', None),
                           username=jfrog_section.get('username', None),
                           password=jfrog_section.get('password', None))

        robot_section: configparser.SectionProxy = config['robot_framework']
        self.robot = RobotConfig(tests_dir=robot_section.get('robot_tests_dir', None),
                                 reports_dir=robot_section.get('robot_reports_dir', None),
                                 tests=robot_section.get('robot_tests', []))

        pxe_server_section: configparser.SectionProxy = config['pxe_server']
        self.pxe_server = PXEServerConfig(ip_address=pxe_server_section.get('ip_address', None),
                                          filesystem_root=pxe_server_section.get('pxe_filesystem_root', None),
                                          working_dir=pxe_server_section.get('working_dir', None),
                                          sdcard_image_path=pxe_server_section.get('sdcard_image_path', None),
                                          artifacts_dir=pxe_server_section.get('artifacts_dir', None),
                                          logs_dir=pxe_server_section.get('logs_dir', None))

        csl_nodes: List[str] = [csl_node for csl_node in config if 'comms_sleeve' in csl_node]
        for csl_node in csl_nodes:
            section: configparser.SectionProxy = config[csl_node]
            self.csl_nodes.append(CSLNode(hostname=section.get('hostname', None),
                                          ip_address=section.get('ip_address', None),
                                          mac_address=section.get('mac_address', None),
                                          username=section.get('username', None),
                                          password=section.get('password', None),
                                          port=section.getint('port', 0),
                                          router_port_link=section.getint('router_port_link', 0),
                                          nfs_folder_name=section.get('nfs_folder_name', None)))

    @classmethod
    def get_configuration(cls) -> Configuration:
        if not Configuration.__instance__:
            Configuration.__instance__ = Configuration()
            Configuration.__instance__.__parse_configuration()
        return Configuration.__instance__

    def __repr__(self) -> str:
        return (f'Configuration(\n\t{self.router}\n\t{self.jfrog}\n\t{self.pxe_server}'
                f'\n\t{self.csl_nodes}\n\t{self.robot}\n)')
