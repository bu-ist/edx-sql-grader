#!/usr/bin/env python
import logging.config

import settings
from graders import GraderDaemon

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,

    'formatters': {
        'verbose': {
            'format': settings.LOG_FORMAT,
            # 'datefmt': '%H:%M:%S',
            },
        'console': {
            'format': '[%(asctime)s][%(levelname)s] %(name)s %(filename)s:%(funcName)s:%(lineno)d | %(message)s',
            'datefmt': '%H:%M:%S',
            },
        },

    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
            },
        'sentry': {
            'level': 'WARNING',
            'class': 'raven.handlers.logging.SentryHandler',
            'dsn': settings.SENTRY_DSN
            },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'verbose',
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
    logging.config.dictConfig(LOGGING)

    grader = GraderDaemon().start()
