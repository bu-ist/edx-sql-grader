import time
import logging

import settings
from xqueue import XQueueClient
from .manager import GraderManager

log = logging.getLogger(__name__)


class GraderDaemon():
    def __init__(self):
        self.xqueue = XQueueClient(**settings.XQUEUE_INTERFACE)
        self.poll_interval = settings.POLL_INTERVAL

    def start(self):
        for submission in self.get_submissions():
            reply = self.handle_submission(submission)
            self.send_reply(submission, reply)

    def get_submissions(self):
        while True:
            submission = self.xqueue.get_submission()
            if submission:
                yield submission
            time.sleep(self.poll_interval)

    def handle_submission(self, submission):
        grader = GraderManager.create(submission)

        if grader:
            reply = grader.grade(submission)
        else:
            reply = {
                "correct": False,
                "score": 0,
                "msg": "<p>Could not grade response. Please contact course staff.</p>",
                "grader_id": str(self)
            }
        return reply

    def send_reply(self, submission, reply):
        success, message = self.xqueue.put_result(submission, reply)
        if not success:
            log.error("Error posting reply: %s", message)
