import logging
from typing import List, Optional
from common.CommandRunner import ICommandRunner
from logger.Logger import init_logger
from router.POEPort import POEPort


class MikroTikClient(object):

    NEW_LINE_DELIMITER: str = '\n'
    COMMENT_PREFIX: str = ';;;'

    def __init__(self, command_runner: ICommandRunner) -> None:
        self.command_runner: ICommandRunner = command_runner
        self.logger: logging.Logger = init_logger()

    def get_poe_ports(self) -> List[POEPort]:
        cmd: str = 'interface ethernet poe print without-paging'
        self.logger.debug(f'Running command "{cmd}"')
        output, code = self.command_runner.exec(cmd)
        if 0 != code:
            return []

        return self.parse_interface_ethernet_poe_cmd(output)

    def get_poe_ports_by_name(self, port_name: str) -> Optional[POEPort]:
        ports: List[POEPort] = [port for port in self.get_poe_ports() if port.name == port_name]
        return ports[0] if ports else None

    def set_poe_port_power(self,
                           port_name: str,
                           state: POEPort.Power) -> bool:
        cmd: str = f'interface ethernet poe set {port_name} poe-out={state.value}'
        self.logger.debug(f'Running command "{cmd}"')
        output, code = self.command_runner.exec(cmd)
        return 0 == code

    def power_on_poe_port(self, port_name: str) -> bool:
        return self.set_poe_port_power(port_name,  POEPort.Power.On)

    def power_off_poe_port(self, port_name: str) -> bool:
        return self.set_poe_port_power(port_name,  POEPort.Power.Off)

    @staticmethod
    def parse_interface_ethernet_poe_cmd(output: str) -> List[POEPort]:
        lines: List[str] = [ln.strip() for ln in output.split(MikroTikClient.NEW_LINE_DELIMITER)
                            if ln and MikroTikClient.COMMENT_PREFIX not in ln]

        ports: List[POEPort] = []
        for line in lines:
            if line.startswith('#') or line.startswith('Columns'):
                continue

            parts: List[str] = line.split()
            if 8 != len(parts):
                continue

            poe: POEPort = POEPort(parts[1])
            poe.state = POEPort.Power.from_string(parts[2])
            poe.voltage = POEPort.Voltage.from_string(parts[3])
            poe.priority = parts[4]
            poe.lldp_enabled = parts[5]
            poe.cycle_ping_enabled = parts[6]

            ports.append(poe)

        return ports
