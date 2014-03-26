#!/usr/bin/env python
import logging.config

import settings
from graders import GraderDaemon

LOG_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,

    'formatters': {
        'default': {
            'format': settings.LOG_FORMAT,
            },
        },

    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'default'
            },
        'file': {
            'level': settings.LOG_LEVEL,
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'default',
            'filename': settings.DAEMON_LOG,
            'maxBytes': 20480,
            'backupCount': 3,
            },
        },

    'loggers': {
        '': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False
            }
    }
}


if __name__ == "__main__":
    logging.config.dictConfig(LOG_CONFIG)
    grader = GraderDaemon().start()
