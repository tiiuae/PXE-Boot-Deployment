import logging
import sys
import os

import tempfile
from common.CSLNode import CSLNode
from pathlib import Path
from typing import List, Tuple
from logger.Logger import init_logger
from utils.Utilities import run_command, FileUtilities
from config.Configuration import Configuration


class ImageWrapper(object):
    BOOT_FS_DIR_NAME: str = 'boot'
    ROOT_FS_DIR_NAME: str = 'rootfs'
    TFTP_ROOT_DIR_NAME: str = 'tftpboot'

    SSHD_CONFIG_PATH: str = '/etc/ssh/sshd_config'
    FSTAB_CONFIG_PATH: str = '/etc/fstab'
    HOSTNAME_FILE_PATH: str = '/etc/hostname'
    CMDLINE_FINE_NAME: str = 'cmdline.txt'

    HOSTS_FILE_PATH: str = '/etc/hosts'

    def __init__(self,
                 image_path: str,
                 server_ip_address: str) -> None:
        self.config: Configuration = Configuration.get_configuration()
        self.logger: logging.Logger = init_logger()

        self.pxe_fs_root: str = self.config.pxe_server.filesystem_root
        self.img_path: Path = Path(image_path)
        self.server_ip_address: str = server_ip_address

    class LoopContext(object):

        def __init__(self,
                     file_path: str,
                     logger: logging.Logger) -> None:
            self.logger: logging.Logger = logger
            self.file_path: str = file_path
            self.loop: str = ""

        def __enter__(self) -> str:
            self.logger.debug(f'\tCreating the file {self.file_path} association with loop device')
            output, status = run_command(cmd=f'losetup --show -fP {self.file_path}', print_output=False)
            if not output:
                raise RuntimeError(f'Failed to create loop devices for {self.file_path}')
            self.loop = output.split()[0]

            self.logger.debug(f'\tOK. Loop device: {self.loop}')
            return self.loop

        def __exit__(self,
                     exc_type,
                     exc_val,
                     exc_tb) -> None:
            self.logger.debug(f'\tDetaching the loop device {self.loop} association')
            output, status = run_command(cmd=f'losetup -d {self.loop}', print_output=False)
            if 0 != status:
                raise RuntimeError(f'Failed to close loop devices for {self.file_path}. Status = {status}')

            self.logger.debug(f'\tOK')

    class MountContext(object):

        def __init__(self,
                     device: str,
                     mount_point: str,
                     logger: logging.Logger) -> None:
            self.logger: logging.Logger = logger
            self.device: str = device
            self.mount_point: str = mount_point

        def __enter__(self):
            self.logger.debug(f'\tMounting {self.device} to {self.mount_point}')
            output, status = run_command(cmd=f'mount -o ro {self.device} {self.mount_point}', print_output=False)
            if 0 != status:
                raise RuntimeError(f'Failed to mount device "{self.device}" to "{self.mount_point}". '
                                   f'Status = {status}. output: {output}')

            self.logger.debug(f'\tOK')
            return self

        def __exit__(self,
                     exc_type,
                     exc_val,
                     exc_tb) -> None:
            self.logger.debug(f'\tUnmounting {self.device} to {self.mount_point}')
            output, status = run_command(cmd=f'umount {self.mount_point}', print_output=False)
            if 0 != status:
                raise RuntimeError(f'Failed to umount "{self.mount_point}". Status = {status}. Output: {output}')

            self.logger.debug(f'\tOK')

    class NFSServiceContext(object):

        def __init__(self,
                     logger: logging.Logger) -> None:
            self.logger: logging.Logger = logger

        def __enter__(self):
            self.logger.debug(f'\tStopping the NFS Server service')
            output, err_code = run_command('service nfs-kernel-server stop')
            if err_code:
                raise RuntimeError(f'Failed to stop "nfs-kernel-server" service. Output: {output}')

            self.logger.debug(f'\tOK')
            return self

        def __exit__(self, exc_type, exc_val, exc_tb) -> None:
            self.logger.debug(f'\tStarting the NFS Server service')
            output, err_code = run_command('service nfs-kernel-server start')
            if err_code:
                raise RuntimeError(f'Failed to start "nfs-kernel-server" service. Output: {output}')
            self.logger.debug(f'\tOK')

    @staticmethod
    def copy_partition(src_dir: str, dst_dir: str) -> bool:
        # Trying to create directory, ignore is its already exits
        Path(dst_dir).mkdir(parents=True, exist_ok=True)

        # Copy all files to the destination directory:
        cmd: str = f'cp -ar {src_dir}/. {dst_dir}'
        _, err_code = run_command(cmd)
        if err_code:
            sys.stderr.write(f'"{cmd}" failed')
            return False

        return True

    def unpack_image(self,
                     boot_dir: str,
                     root_dir: str) -> bool:
        """
        Decompresses/extracts data from an image for HardenedOS
        Filesystem structure:
        - boot files are contained in the directory: /pxe/<CSL_MAC>/boot
        - root files are contained in the directory: /pxe/<CSL_MAC>/rootfs

        Execution Steps:
        1. Check is the image exists
        2. Stop the NFS service
        3. Create a temporary folder using the tempfile Python module
        4. Create a control loop device for the image file
        5. Mount the first partition (p1) of the loop device, copy all files to the local boot NFS directory for
           this CSL and unmount the p1 partitions of the image
        6. Mount the second partition (p2) of the loop device, copy all files to the local root NFS directory for
           this CSL and unmount the p2 partitions of the image
        7. Close the previously created loop device
        8. Remove the previously created temporary file
        9. Start the NFS service

        :param boot_dir: Path to CSL-specific boot filesystem dir (/pxe/<CSL_MAC>/boot)
        :param root_dir: Path to CSL-specific root filesystem dir (/pxe/<CSL_MAC>/rootfs)
        :return: True or False
        """

        self.logger.debug(f'\tUnpacking the SDCard image {self.img_path.absolute()}')
        if not self.img_path.exists() or not self.img_path.is_file():
            raise RuntimeError(f'Image file {self.img_path.absolute()} do not exists')

        with self.NFSServiceContext(self.logger) as _:

            csl_root: str = str(Path(boot_dir).parent)
            self.logger.debug(f'\tRemove the old {csl_root}')
            _, err_code = run_command(f'rm -rf {csl_root}')
            if err_code:
                self.logger.error(f'Failed to remove dir: {csl_root}')
                return False

            with tempfile.TemporaryDirectory() as tmp_dir:
                with self.LoopContext(str(self.img_path), self.logger) as loop:
                    with self.MountContext(loop + 'p1', tmp_dir, self.logger) as _:
                        if not ImageWrapper.copy_partition(tmp_dir, boot_dir):
                            return False
                    with self.MountContext(loop + 'p2', tmp_dir, self.logger) as _:
                        if not ImageWrapper.copy_partition(tmp_dir, root_dir):
                            return False
        return True

    @staticmethod
    def create_tftp_boot_symlink(boot_dir: str,
                                 csl_tftp_boot_dir: str) -> bool:
        cmd: str = f'ln -fsn {boot_dir}/ {csl_tftp_boot_dir}'
        _, err_code = run_command(cmd, print_output=False)
        if err_code:
            sys.stderr.write(f'"{cmd}" failed')
            return False

        return True

    def configure_csl_filesystem(self,
                                 boot_dir: str,
                                 root_dir: str,
                                 server_ip_address: str,
                                 csl_ip_addr: str,
                                 csl_hostname: str) -> None:

        ssh_config_path: str = f'{root_dir}{ImageWrapper.SSHD_CONFIG_PATH}'
        fstab_path: str = f'{root_dir}{ImageWrapper.FSTAB_CONFIG_PATH}'
        hostname_file_path: str = f'{root_dir}/{ImageWrapper.HOSTNAME_FILE_PATH}'
        cmdline_path: str = f'{boot_dir}/{ImageWrapper.CMDLINE_FINE_NAME}'

        self.modify_sshd_config(ssh_config_path)
        self.modify_fstab_file(boot_dir, fstab_path, server_ip_address)
        self.modify_cmdline_file(root_dir, cmdline_path, server_ip_address)
        self.set_cls_hostname(hostname_file_path, csl_hostname)

        # FIXME
        # ImageWrapper.add_host_on_server(csl_ip_addr, csl_hostname)

    def modify_fstab_file(self,
                          boot_dir: str,
                          fstab_path: str,
                          ip_address: str) -> bool:
        self.logger.debug(f'\tConfiguring the CSL fstab config: File path: {fstab_path}')
        lines: List[str] = FileUtilities.read_file_lines(fstab_path)
        if not lines:
            return False

        root_idx: int = -1
        for idx, line in enumerate(lines):
            params: List[str] = line.split()
            if len(params) > 1 and '/' == params[1]:
                root_idx = idx
                break

        if -1 == root_idx:
            return False

        lines[root_idx] = f'{ip_address}:{boot_dir} /boot nfs defaults,vers=4.1,tcp 0 0'
        FileUtilities.write_lines_to_file(fstab_path, lines)
        return True

    def modify_sshd_config(self, ssh_config_path: str) -> bool:
        lines: List[str] = FileUtilities.read_file_lines(ssh_config_path)
        if not lines:
            return False

        # TODO: Fix me check if it could be more names with 'PasswordAuthentication' and etc
        replacements: List[Tuple[str, str]] = [
            ('PermitRootLogin', 'PermitRootLogin yes'),
            ('PasswordAuthentication', 'PasswordAuthentication yes'),
            ('/etc/ssh/ssh_host_rsa_key', 'HostKey /etc/ssh/ssh_host_rsa_key')
        ]
        for idx, line in enumerate(lines):
            for substr, new_value in replacements:
                if substr in line:
                    lines[idx] = new_value

        self.logger.debug(f'\tConfiguring the CSL sshd config: File path: {ssh_config_path}')
        FileUtilities.write_lines_to_file(ssh_config_path, lines)
        return True

    @staticmethod
    def add_host_on_server(ip: str, hostname: str):
        lines: List[str] = FileUtilities.read_file_lines(ImageWrapper.HOSTS_FILE_PATH)
        has_to_add_new: bool = True
        for idx, line in enumerate(lines):
            # Keep empty lines and comments
            if len(line) and not line.startswith('#'):
                print(line)
                host_ip, name = line.split(sep=' ', maxsplit=1)
                host_ip, name = host_ip.strip(), name.strip()
                if host_ip == ip and name == hostname:
                    return
                elif host_ip == ip and name != hostname:
                    lines[idx] = line.replace(name, hostname)
                    has_to_add_new = False

        if has_to_add_new:
            lines.append(f"{ip:<18}{hostname}")
        FileUtilities.write_lines_to_file(ImageWrapper.HOSTS_FILE_PATH, lines)

    def set_cls_hostname(self,
                         hostname_file_path: str,
                         hostname: str):
        self.logger.debug(f'\tSet CSL hostname: Updating the file {hostname_file_path}. new content: {hostname}')
        FileUtilities.write_lines_to_file(hostname_file_path, [hostname])

    def modify_cmdline_file(self,
                            root_dir: str,
                            cmdline_path: str,
                            ip_address: str) -> bool:
        cmdline: str = (f'rootwait console=tty1 console=ttyS0,115200 pcie_aspm=off selinux=1 enforcing=0 '
                        f'ip=dhcp root=/dev/nfs nfsroot={ip_address}:{root_dir},vers=4.1,proto=tcp')

        self.logger.debug(f'\tUpdating the cmdfile {cmdline_path} to "{cmdline}"')
        FileUtilities.write_lines_to_file(cmdline_path, [cmdline])
        return True

    @staticmethod
    def copy_ssh_keys(root_dir: str):
        deployment_dir: str = os.path.dirname(os.path.realpath(__file__))
        ssh_keys_dir: str = f'{deployment_dir}/ssh_keys'

        for key_file, mode in [('ssh_host_rsa_key.pub', 664), ('ssh_host_rsa_key', 600)]:
            run_command(f'cp {ssh_keys_dir}/{key_file} {root_dir}/etc/ssh/{key_file}')
            run_command(f'chmod {mode} {root_dir}/etc/ssh/{key_file}')

    def prepare_pxe_boot_configuration(self,
                                       node: CSLNode) -> bool:
        mac_address, ip_address, hostname = node.mac_address, node.ip_address, node.hostname
        self.logger.debug(f'Preparing NFS filesystem for device '
                          f'MAC: {mac_address}, IP: {ip_address}, Hostname: {hostname}')

        # If the 'nfs_folder_name' attribute is specified then it will be used as the NFS filesystem
        # folder for the CommsSleeve, otherwise name will be generated automatically from the node's MAC
        # address just by removing the ':' symbols from it
        nfs_dir_name: str = node.nfs_folder_name if node.nfs_folder_name else mac_address.replace(':', '')

        csl_root_folder = f'{self.pxe_fs_root}/{nfs_dir_name}'

        boot_dir: str = f'{csl_root_folder}/{self.BOOT_FS_DIR_NAME}'
        self.logger.debug(f'\tCSL NSF Boot dir: {boot_dir}')

        root_dir: str = f'{csl_root_folder}/{self.ROOT_FS_DIR_NAME}'
        self.logger.debug(f'\tCSL NSF Root dir: {root_dir}')

        tftp_root_dir: str = f'{self.pxe_fs_root}/{self.TFTP_ROOT_DIR_NAME}'
        csl_tftp_boot_dir_name: str = mac_address.replace(':', '-')
        csl_tftp_boot_dir: str = f'{tftp_root_dir}/{csl_tftp_boot_dir_name}'

        self.logger.debug(f'\tCSL TFTP Boot dir: {csl_tftp_boot_dir}')

        if not self.unpack_image(boot_dir, root_dir):
            return False
        self.configure_csl_filesystem(boot_dir, root_dir,
                                      self.server_ip_address, ip_address, hostname)

        self.logger.debug(f'\tCreating Symlink {csl_tftp_boot_dir} --> {boot_dir}')
        if not self.create_tftp_boot_symlink(boot_dir, csl_tftp_boot_dir):
            return False

        # self.copy_ssh_keys(root_dir)

        return False
