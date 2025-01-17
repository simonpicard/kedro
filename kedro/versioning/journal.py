"""This module provides journal logging to enable versioning support for
Kedro project."""
import json
import logging
import subprocess
import warnings
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Union

_JOURNAL_KEY = "kedro.journal"


class Journal:
    """``Journal`` class provides journal logging to enable versioning support for
    Kedro project.
    """

    def __init__(self, record_data: Dict[str, Any]):
        """Initialise ``Journal`` as a session of the journal versioning,
        and log the project context with an unique identifier.

        Args:
            record_data: JSON serializable dictionary specific to project context.
        Raises:
            DeprecationWarning
        """
        warnings.warn(
            "`Journal` is now deprecated and will be removed in Kedro 0.18.0."
            "For more information, please visit "
            "https://github.com/quantumblacklabs/kedro/blob/master/RELEASE.md",
            DeprecationWarning,
        )

        self.run_id = record_data["run_id"]
        record_data["git_sha"] = _git_sha(record_data["project_path"])
        self._log_journal("ContextJournalRecord", record_data)

    def _log_journal(self, record_type: str, record_data: Mapping) -> None:
        """Log a record to journal.

        Args:
            record_type: A unique type identifier.
            record_data: JSON serializable dictionary, specific to ``record_type``.

        """
        # pylint: disable=no-self-use
        try:
            logging.getLogger(_JOURNAL_KEY).info(
                json.dumps({"type": record_type, **record_data})
            )
        except TypeError:
            logging.getLogger(__name__).error(
                "Unable to record %s to journal, make sure it's a "
                "serializable dictionary",
                repr(record_data),
            )

    def log_catalog(
        self, dataset_name: str, operation: str, version: str = None
    ) -> None:
        """Log journal record for ``DataCatalog``.

        Args:
            dataset_name: Name of dataset being logged.
            operation: Operation on dataset, one of {'save', 'load'}.
            version: Dataset version corresponding to operation (i.e if operation
                is "save" then this is "save_version").

        """
        record_data = {
            "run_id": self.run_id,
            "name": dataset_name,
            "operation": operation,
            "version": version,
        }
        self._log_journal("DatasetJournalRecord", record_data)


def _git_sha(proj_dir: Union[str, Path] = None) -> Optional[str]:
    """Git description of working tree.

    Returns: Git description or None.

    """
    proj_dir = str(proj_dir or Path.cwd())
    try:
        res = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=proj_dir
        )
        return res.decode().strip()
    # `subprocess.check_output()` raises `NotADirectoryError` on Windows
    except (subprocess.CalledProcessError, FileNotFoundError, NotADirectoryError):
        logging.getLogger(__name__).warning("Unable to git describe %s", proj_dir)
    return None


class JournalFileHandler(logging.Handler):
    """Handler for logging journal record to a file based on journal ID."""

    def __init__(self, base_dir: Union[str, Path]):
        """Initialise ``JournalFileHandler`` which will handle logging journal record.

        Args:
            base_dir: Base directory for saving journals.

        """
        super().__init__()
        self.base_dir = Path(base_dir).expanduser()
        self._file_handlers = {}  # type:Dict[str, logging.FileHandler]

    def _generate_handler(self, run_id: str) -> logging.FileHandler:
        """Generate unique filename for journal record path.

        Returns:
            Logging FileHandler object.

        """
        self.base_dir.mkdir(parents=True, exist_ok=True)
        handler_path = self.base_dir.resolve() / f"journal_{run_id}.log"
        return logging.FileHandler(str(handler_path), mode="a")

    def emit(self, record: logging.LogRecord) -> None:
        """Overriding emit function in logging.Handler, which will output the record to
        the filelog based on run id.

        Args:
            record: logging record.

        """
        message = json.loads(record.getMessage())

        handler = self._file_handlers.setdefault(
            message["run_id"], self._generate_handler(message["run_id"])
        )

        handler.emit(record)
