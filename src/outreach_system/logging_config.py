import contextvars
import logging

_execution_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "execution_id",
    default="-",
)


class ExecutionIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.execution_id = _execution_id.get()
        return True


def set_execution_id(value: str) -> None:
    _execution_id.set(value)


def configure_logging(level: str) -> None:
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            handler.addFilter(ExecutionIdFilter())
        root.setLevel(level.upper())
        return

    logging.basicConfig(
        level=level.upper(),
        format=(
            "%(asctime)s %(levelname)s [%(name)s] "
            "[run=%(execution_id)s] %(message)s"
        ),
    )
    for handler in logging.getLogger().handlers:
        handler.addFilter(ExecutionIdFilter())
