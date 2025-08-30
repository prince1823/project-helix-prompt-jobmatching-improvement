import logging
from logging.handlers import TimedRotatingFileHandler
from app.core.config import config

# create logger
logger = logging.getLogger("whatsapp_bot")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s - %(thread)d - %(process)d - %(pathname)s - %(filename)s:%(lineno)d - %(funcName)s - %(levelname)s - %(message)s"
)

# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)

fh = TimedRotatingFileHandler(
    config["logger"]["file_path"] + "whatsapp-bot-py.log",
    when="midnight",
    backupCount=7,
)
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)

# add ch to logger
logger.addHandler(ch)
logger.addHandler(fh)
