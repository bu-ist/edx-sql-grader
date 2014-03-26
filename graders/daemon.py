import time
import logging

from lxml import etree
from statsd import statsd

import settings
from xqueue import XQueueClient

from .manager import GraderManager
from .exceptions import InvalidGraderResponse

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
        fail_reply = {
            "correct": False,
            "score": 0,
            "msg": "<p>Could not grade submission. Please contact course staff.</p>",
            "grader_id": str(self)
        }

        grader = GraderManager.create(submission)
        if not grader:
            statsd.increment('grader.handle.fail')
            return fail_reply

        reply = grader.grade(submission)

        try:
            self.validate_reply(reply)
        except InvalidGraderResponse as e:
            # TODO: use log.exception instead
            log.critical("Invalid grader reply for submission %d", submission["id"])
            log.critical("Reply: %s", reply)
            log.critical("Reason: %s", e)
            return fail_reply

        statsd.increment('grader.handle.success')
        return reply

    def send_reply(self, submission, reply):
        success, message = self.xqueue.put_result(submission, reply)
        if not success:
            log.error("Error posting reply: %s", message)

    def validate_reply(self, reply):
        if not isinstance(reply, dict):
            raise InvalidGraderResponse("Grader reply is not a dict")

        for required_key in ['correct', 'score', 'msg', 'grader_id']:
            if required_key not in reply:
                raise InvalidGraderResponse("Grader reply dict missing required key: %s" % required_key)

        # Run the response msg through the same XML parser that the LMS uses to catch syntax errors
        # See `_parse_score_msg` in edx-platform/common/lib/capa/capa/responsetypes.py
        try:
            etree.fromstring(reply['msg'])
        except etree.XMLSyntaxError as e:
            raise InvalidGraderResponse("Grader reply contains invalid XML. Error: %s", e)
