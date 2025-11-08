"""Base command class for CLI commands."""

import logging
from abc import ABC, abstractmethod
from argparse import ArgumentParser, Namespace
from typing import Any, Dict, Optional

from ...core.error_handling import MicroWeldrError, handle_errors, error_context

logger = logging.getLogger(__name__)


class BaseCommand(ABC):
    """Base class for CLI commands."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add command-specific arguments to the parser."""
        pass

    @abstractmethod
    def execute(self, args: Namespace) -> bool:
        """Execute the command. Return True on success, False on failure."""
        pass

    @handle_errors(log_errors=True, reraise=False)
    def run(self, args: Namespace) -> bool:
        """Run the command with error handling."""
        with error_context(f"command_{self.name}", command=self.name):
            logger.info(f"Executing command: {self.name}")

            try:
                result = self.execute(args)
                if result:
                    logger.info(f"Command {self.name} completed successfully")
                else:
                    logger.error(f"Command {self.name} failed")
                return result
            except MicroWeldrError as e:
                logger.error(f"Command {self.name} failed: {e.message}")
                if hasattr(args, "verbose") and args.verbose:
                    logger.error(f"Error details: {e.details}")
                return False
            except Exception as e:
                logger.error(f"Unexpected error in command {self.name}: {e}")
                return False

    def get_common_config(self, args: Namespace) -> Dict[str, Any]:
        """Get common configuration from arguments."""
        config = {}

        if hasattr(args, "verbose"):
            config["verbose"] = args.verbose
        if hasattr(args, "quiet"):
            config["quiet"] = args.quiet
        if hasattr(args, "config"):
            config["config_path"] = args.config
        if hasattr(args, "log_file"):
            config["log_file"] = args.log_file

        return config
