import logging
import sys
import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | request_id=%(request_id)s | %(message)s"


def setup_logging() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("linkhub.log"),
        ],
    )

    class RequestIdFilter(logging.Filter):
        def filter(self, record):
            record.request_id = request_id_var.get("")
            return True

    logger = logging.getLogger("linkhub")
    logger.addFilter(RequestIdFilter())
    return logger


logger = setup_logging()
