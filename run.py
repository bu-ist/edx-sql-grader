#!/usr/bin/env python
import daemon
import logging
from pwd import getpwnam
from grp import getgrnam
import os

import settings
from graders import GraderDaemon

if __name__ == "__main__":

    output = file(settings.OUT_LOG, 'a')

    context = daemon.DaemonContext(
        detach_process=(not settings.DAEMON_DEBUG),
        stdout=output,
        stderr=output,
        working_directory=os.path.dirname(os.path.abspath(__file__)),
        uid=getpwnam(settings.DAEMON_USER).pw_uid,
        gid=getgrnam(settings.DAEMON_GROUP).gr_gid,
        umask=2,
    )

    with context:
        logging.basicConfig(level=settings.LOG_LEVEL,
                            filename=settings.DAEMON_LOG,
                            format=settings.LOG_FORMAT)
        grader = GraderDaemon().start()
