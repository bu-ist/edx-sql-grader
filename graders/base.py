

class BaseGrader(object):
    """ Base class for edX External Graders """

    def grade(self):
        """
        Abstract - subclasses must implement
        """
        raise NotImplementedError
