import logging

import settings

from .grader import SQLiteGrader, MySQLGrader, S3UploaderMixin
from .exceptions import InvalidGrader

log = logging.getLogger(__name__)


class GraderManager(object):
    """ Instantiates Grader objects given an xqueue submission """

    @staticmethod
    def create(submission):
        grader_type = submission['grader_payload'].get('grader', "mysql")

        if grader_type not in settings.GRADER_CONFIG:
            log.critical("Improperly configured grader %s", grader_type)
            return False

        # Map grader type to class name -- bailing if none is found
        if grader_type == 'sqlite':
            Grader = SQLiteGrader
        elif grader_type == 'mysql':
            Grader = MySQLGrader
        else:
            return False

        # Base configuration
        config = {}

        # Grader configuration
        config.update(settings.GRADER_CONFIG[grader_type])

        # S3 Configuration if grader supported
        if issubclass(Grader, S3UploaderMixin):
            config.update({
                "s3_bucket": settings.GRADER_S3_BUCKET,
                "s3_prefix": settings.GRADER_S3_PREFIX,
                "aws_access_key": settings.AWS_ACCESS_KEY,
                "aws_secret_key": settings.AWS_SECRET_KEY
                })

        # Merge grader payload with our configuration
        config.update(submission['grader_payload'])

        try:
            grader = Grader(**config)
        except InvalidGrader as e:
            log.critical("Could not create grader: %s", e)
            grader = False

        return grader
