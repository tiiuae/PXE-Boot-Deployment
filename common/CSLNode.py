from dataclasses import dataclass
from typing import Optional


@dataclass
class CSLNode(object):
    hostname: str      # host name of the CSL
    ip_address: str    # IP address of the CSL ethernet interface
    mac_address: str   # MAC address of the CSL ethernet interface
    username: str
    password: str
    port: int               # for SSH
    router_port_link: int   # Ethernet port/link on the Router
    nfs_folder_name: Optional[str] = None
