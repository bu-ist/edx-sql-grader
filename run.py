#!/usr/bin/env python
import logging

import settings
from graders import GraderDaemon

if __name__ == "__main__":
    logging.basicConfig(level=settings.LOG_LEVEL,
                        format=settings.LOG_FORMAT)
    grader = GraderDaemon().start()
