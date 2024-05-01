import logging
import time

from typing import List
from logger.Logger import init_logger
from router.POEPort import POEPort
from common.CSLNode import CSLNode
from ssh.SSHClient import SSHClient
from utils.Utilities import wait_for_ports, wait_for_hosts
from deployment.PreparePXEBootFS import ImageWrapper
from router.MikroTikClient import MikroTikClient
from integration.Artifactory import Artifactory
from config.Configuration import Configuration, Router, JFrog, PXEServerConfig


class Deployment(object):

    CSL_WAIT_FOR_BOOT_TIMEOUT: float = 60.0 * 5.0
    CSL_BOOT_WARN_TIMEOUT: float = CSL_WAIT_FOR_BOOT_TIMEOUT * 2

    def __init__(self):
        self.config: Configuration = Configuration.get_configuration()
        self.logger: logging.Logger = init_logger()

        self.router_config: Router = self.config.router
        self.jfrog_config: JFrog = self.config.jfrog
        self.pxe_server_config: PXEServerConfig = self.config.pxe_server

        ssh_client = SSHClient(hostname=self.router_config.host,
                               username=self.router_config.username,
                               password=self.router_config.password)

        self.router_client: MikroTikClient = MikroTikClient(ssh_client)
        self.artifactory: Artifactory = Artifactory(host=self.jfrog_config.host,
                                                    username=self.jfrog_config.username,
                                                    password=self.jfrog_config.password)

        self.image_path: str = self.config.pxe_server.sdcard_image_path
        self.wrapper: ImageWrapper = ImageWrapper(image_path=self.pxe_server_config.sdcard_image_path,
                                                  server_ip_address=self.pxe_server_config.ip_address)

    def switch_comms_sleeves_power(self,
                                   csl_list: List[CSLNode],
                                   state: POEPort.Power) -> bool:
        ports_names: List[str] = [f'ether{node.router_port_link}' for node in csl_list]
        for ether_port in ports_names:
            self.logger.debug(f'Powering \'{state}\' the {ether_port} . . .')
            if not self.router_client.set_poe_port_power(ether_port, state):
                self.logger.error(f'ERROR: Failed to set PoE port {ether_port} to {state} state')
                return False
            self.logger.debug(f'Done')

        self.logger.debug(f"Checking the CommsSleeve's states...")
        ports: List[POEPort] = self.router_client.get_poe_ports()
        if not ports:
            self.logger.error(f'ERROR: Empty PoE ports list is returned')
            return False

        for poe_port in ports:
            if poe_port.name in ports_names and poe_port.state != state:
                self.logger.error(f'ERROR: PoE port {poe_port.name} is in {poe_port.state} state. ({state} expected)')
                return False

        return True

    def deploy(self,
               nodes: List[CSLNode]) -> bool:
        self.logger.debug('Comms Sleeves to re-Boot:')
        for node in nodes:
            self.logger.debug(f'\t\t{node}')

        if not self.switch_comms_sleeves_power(nodes, POEPort.Power.Off):
            return False

        self.logger.debug('Preparing the PXE boot NFS filesystem......')
        for node in nodes:
            # TODO: Check result
            result: bool = self.wrapper.prepare_pxe_boot_configuration(node)

        if not self.switch_comms_sleeves_power(nodes, POEPort.Power.On):
            return False

        self.logger.debug('Waiting for the CSL to boot.....')

        boot_start_time: float = time.time()
        wait_for_hosts([node.ip_address for node in nodes], timeout=self.CSL_WAIT_FOR_BOOT_TIMEOUT)
        wait_for_ports([node.ip_address for node in nodes], timeout=self.CSL_WAIT_FOR_BOOT_TIMEOUT, port=22)
        boot_duration: float = time.time() - boot_start_time

        if boot_duration > self.CSL_BOOT_WARN_TIMEOUT:
            self.logger.warning(f"CSL'=s boot took longer than expected: {boot_duration} seconds")

        # TODO: print --> logging
        print('==' * 90, '\n', '\t' * 7, boot_duration, '\n', '==' * 90, sep='')

        return True
