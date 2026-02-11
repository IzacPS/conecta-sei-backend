import logging
from colorlog import ColoredFormatter


def setup_logger(level=logging.DEBUG):
    # 🟢 Configurar logger root (pega todos os loggers automaticamente)
    logger = logging.getLogger()  
    logger.setLevel(level)

    # Evitar handlers duplicados
    if logger.hasHandlers():
        logger.handlers.clear()

    # Formatação colorida
    formatter = ColoredFormatter(
        "%(log_color)s%(levelname)-8s%(reset)s | "
        "%(blue)s%(asctime)s%(reset)s | "
        "%(green)s%(name)s:%(lineno)d%(reset)s | "
        "%(white)s%(message)s",
        datefmt="%d-%m-%Y %H:%M:%S",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "white",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold_red,bg_white",
        },
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    return logger