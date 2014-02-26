#!/usr/bin/env python
import logging
import time

import settings

from util import XQueueClient
from graders import GraderManager


def start():
    """ Poll xqueue listening for submissions """
    try:
        xqueue = XQueueClient(**settings.XQUEUE_INTERFACE)

        while True:
            submission = xqueue.get_submission()
            if submission:
                grader = GraderManager.create(submission)
                if grader:
                    reply = grader.grade(submission)
                else:
                    reply = {
                        "score": 0,
                        "correct": False,
                        "msg": "<p>Could not grade submission. Please contact course staff.</p>"
                    }
                xqueue.put_result(submission, reply)

            time.sleep(settings.POLL_INTERVAL)

    except KeyboardInterrupt:
        print ' KeyboardInterrupt received, Exiting...'


if __name__ == '__main__':
    try:
        log_level = getattr(logging, settings.LOG_LEVEL)
    except AttributeError:
        log_level = logging.ERROR

    logging.basicConfig(level=log_level)
    start()
