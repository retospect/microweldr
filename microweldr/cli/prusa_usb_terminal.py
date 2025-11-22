#!/usr/bin/env python3
"""Entry point wrapper for the Prusa USB Terminal.

This module keeps the implementation DRY by delegating to
scripts.prusa_usb_terminal.main, which is also used by developers
inside the repository.
"""

from scripts.prusa_usb_terminal import main


if __name__ == "__main__":  # pragma: no cover
    main()
