import logging

import settings

from .sql import SQLiteGrader, MySQLGrader
from .exceptions import InvalidGrader

log = logging.getLogger(__name__)


class GraderManager(object):
    """ Instantiates Grader objects given an xqueue submission """

    @staticmethod
    def create(submission):
        engine = submission['grader_payload'].get('engine', 'sqlite')
        database = submission['grader_payload'].get('database', '')

        if engine not in settings.DATABASE:
            log.critical("Improperly configured database engine %s", engine)
            return False

        config = settings.DATABASE[engine]

        if engine == 'sqlite':
            Grader = SQLiteGrader
        elif engine == 'mysql':
            Grader = MySQLGrader
        else:
            return False

        try:
            grader = Grader(db=database, **config)
        except InvalidGrader as e:
            log.critical("Could not create grader: %s", e)
            grader = False

        return grader
