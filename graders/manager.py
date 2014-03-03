import logging

import settings

from .grader import SQLiteGrader, MySQLGrader
from .exceptions import InvalidGrader

log = logging.getLogger(__name__)


class GraderManager(object):
    """ Instantiates Grader objects given an xqueue submission """

    @staticmethod
    def create(submission):
        grader_type = submission['grader_payload'].get('grader', 'sqlite')
        database = submission['grader_payload'].get('database', '')

        if grader_type not in settings.GRADER_CONFIG:
            log.critical("Improperly configured grader %s", grader_type)
            return False

        config = settings.GRADER_CONFIG[grader_type]

        if grader_type == 'sqlite':
            Grader = SQLiteGrader
        elif grader_type == 'mysql':
            Grader = MySQLGrader
        else:
            return False

        try:
            grader = Grader(db=database, **config)
        except InvalidGrader as e:
            log.critical("Could not create grader: %s", e)
            grader = False

        return grader
