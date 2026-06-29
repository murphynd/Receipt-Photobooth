"""Central logging setup -- one clean line per booth event.

Every module does ``from log import log`` and writes ``log.info("PIR: ...")``.
Output goes to stdout, which systemd's journald captures, so

    journalctl -u photobooth -f

tells the whole story of the booth: motion -> beckon -> trigger -> capture ->
print -> cooldown. On the bench (no service) the same lines print to your
terminal.

Knobs (env vars, so the code is identical on the bench and in the service):
    PHOTOBOOTH_LOG_LEVEL   INFO (default) / DEBUG / WARNING ...
"""

import logging
import os
import sys

_CONFIGURED = False


def _configure():
    global _CONFIGURED
    if _CONFIGURED:
        return
    level_name = os.environ.get("PHOTOBOOTH_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    # journald stamps its own wall-clock time + the unit name, but we include a
    # short timestamp too so piped/saved logs are self-describing. The event
    # prefix ("PIR:", "capture:", ...) lives in the message itself, which keeps
    # each line a clean one-liner.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(message)s",
                          datefmt="%Y-%m-%d %H:%M:%S")
    )

    root = logging.getLogger("photobooth")
    root.setLevel(level)
    root.addHandler(handler)
    root.propagate = False
    _CONFIGURED = True


def get_logger():
    """Return the shared, configured booth logger."""
    _configure()
    return logging.getLogger("photobooth")


log = get_logger()
