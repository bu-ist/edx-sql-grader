import logging

from .sqlite import SQLiteGrader
from .exceptions import InvalidGrader

log = logging.getLogger(__name__)


class GraderManager(object):
    """ Instantiates Grader objects given an xqueue submission """

    @staticmethod
    def create(submission):
        engine = submission['grader_payload'].get('engine', 'sqlite')
        database = submission['grader_payload'].get('database', '')

        if engine not in ['sqlite']:
            raise Exception

        if engine == 'sqlite':
            Grader = SQLiteGrader
        else:
            Grader = False

        try:
            grader = Grader(database)
        except InvalidGrader as e:
            log.critical("Could not create grader: %s", e)
            grader = False

        return grader
