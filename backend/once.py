"""Say something in the log once, not on every sentence.

    warn(message)

soul.py, about.py and macros.py each read a file you edit, every single turn,
and each has something to say when that file is wrong or too long. Saying it
on every sentence would train you to stop reading the log, so each complaint
is said the first time and then kept quiet until DONNA restarts.
"""

import logging

_warned = set()


def warn(message):
    if message not in _warned:
        _warned.add(message)
        logging.warning("%s", message)
