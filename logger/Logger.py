import logging.config
from pathlib import Path
from config.Configuration import Configuration

log: logging.Logger = None


def init_logger() -> logging.Logger:

    logging.basicConfig(level=logging.DEBUG)

    # Removing the external loggers tracing:
    logging.getLogger("paramiko.transport").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    logging.getLogger("faker.factory").setLevel(logging.WARNING)

    config = Configuration.get_configuration()
    Path(config.pxe_server.logs_dir).mkdir(parents=True, exist_ok=True)
    file_handler: logging.Handler = logging.FileHandler(f'{config.pxe_server.logs_dir}/deployment.log')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    global log
    if log:
        return log

    log = logging.getLogger(__file__)
    log.addHandler(file_handler)
    log.name = "Deployment"

    return log

