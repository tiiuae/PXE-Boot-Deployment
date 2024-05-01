import subprocess
import sys
import socket
import time
from enum import Enum

from typing import Tuple, List

from ping3 import ping
from scapy.layers.inet import TCP, IP
from scapy.sendrecv import sr1
from scapy.volatile import RandShort


class FileUtilities(object):

    class Mode(Enum):
        ReadText = 'rt'
        Overwrite = 'w'
        Append = 'a'
        CreateAndWrite = 'x'

    @staticmethod
    def read_file_lines(file_path: str,
                        mode: Mode = Mode.ReadText) -> List[str]:
        with open(file_path, mode.value) as file:
            return [raw_line.rstrip('\n') for raw_line in file]

    @staticmethod
    def write_lines_to_file(file_path: str,
                            lines: List[str],
                            mode: Mode = Mode.Overwrite) -> None:
        with open(file_path, mode.value) as file:
            file.writelines([(line + '\n') for line in lines])


def run_command(cmd: str,
                print_output: bool = False,
                shell: bool = False) -> Tuple[str, int]:
    try:
        proc = subprocess.Popen(cmd.split(),
                                text=True,
                                shell=shell,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        output: str = ''
        while True:
            line = proc.stdout.readline()
            if not line:
                break
            if print_output:
                print(str(line.rstrip()).strip("b'"))
                sys.stdout.flush()

            output += line

        proc.wait()
        return output, proc.returncode

    except OSError as exc:
        return f"Can't run process. Error code = {exc}", -1


def is_reachable(host, port, timeout=2):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.settimeout(timeout)
            sock.connect((host, int(port)))
            sock.shutdown(socket.SHUT_RDWR)
            return True
        except:
            return False


def is_host_reachable(host: str) -> bool:
    delay_actual = ping(host, timeout=2)
    return delay_actual is not None


def is_port_open(host: str,
                 port: int,
                 timeout: float = 1.0) -> bool:
    packet = sr1(IP(dst=host) / TCP(sport=RandShort(), dport=port, flags="S"), timeout=timeout, verbose=0)
    return packet and packet.haslayer(TCP) and packet[TCP].flags == 'SA'


def wait_for_hosts(hosts: List[str],
                   timeout: float = 60.0,
                   interval_sec: float = 1.0) -> bool:
    """
    Checks network availability of hosts

    The method in a loop for a specified period of time checks the availability of hosts passed by the input parameter
    1. uses Ping requests to check the availability of hosts
    2. If the host is available, this host is removed from the list
    3. If the list is empty -> returns True
    4. If not all hosts are available within the specified time interval -> False is returned
    5. At each iteration, the timeout value for the Ping request is recalculated to ensure that the
       specified duration of each specific iteration

    :param hosts: List of hosts: [IP's, DNS names and ext]
    :param timeout: maximum duration given in seconds of how long the method waits for the hosts to become available
    :param interval_sec: single loop / iteration duration (in seconds)

    :return: True  - in case if all hosts are available
             False - not all hosts became available during the specified interval
    """

    start: float = time.time()
    while timeout > (time.time() - start):
        # TODO: We may need to remove this division someday
        # ping timeout = [ 1 sec / 'number of hosts' left in list ]
        ping_timeout: float = interval_sec / len(hosts)
        for host in hosts:
            if ping(host, timeout=ping_timeout):
                # remove hosts from the list if It's accessible via ping.
                hosts.remove(host)

        still_unavailable_servers_count: int = len(hosts)
        if 0 == still_unavailable_servers_count:
            return True

    return False


def wait_for_ports(hosts: List[str],
                   port: int = 22,
                   timeout: float = 60.0,
                   interval_sec: float = 1.0) -> bool:
    """
    Waits for the specified TCP port to become open (will transfer to the listening state) on the specified server

    The method in a loop for a specified period of time, checks is the specified port is available:
    1. To check is port is in the listening state method send as SYN packet and waits for a SYN+ACK packet in the response
    2. If the port is opened, this host is removed from the list
    3. If the hosts list becomes empty -> returns True
    4. If not all host's ports are becomes opened within the specified time interval -> False is returned
    5. At each iteration we're trying to ensure that it should last at least one second

    :param hosts: List of hosts: [IP's, DNS names and ext]
    :param port:  port number, to become opened
    :param timeout: maximum duration given in seconds of how long the method waits for the hosts to become available
    :param interval_sec: single loop / iteration duration (in seconds)

    :return: True  - in case if all hosts are available
             False - not all hosts became available during the specified interval
    """

    start: float = time.time()
    while timeout > (time.time() - start):
        iter_start: float = time.time()
        for host in hosts:
            if is_port_open(host=host, port=port):
                hosts.remove(host)

        still_unavailable_servers_count: int = len(hosts)
        if 0 == still_unavailable_servers_count:
            return True

        # To ensure that we will not repeat this loop faster than once per second.
        duration: float = time.time() - iter_start
        if interval_sec > duration:
            time.sleep(interval_sec - duration)

    return False
