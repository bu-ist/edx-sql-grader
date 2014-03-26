import json
import logging
import requests
import time
import urlparse

from statsd import statsd

log = logging.getLogger(__name__)


class XQueueClient():
    """
    XQueue REST client

    Adopted from https://github.com/Stanford-Online/xqueue_pull_ref/blob/master/xqueue_util.py, which
    was largely adopted from https://github.com/edx/edx-ora/blob/master/controller/urls.py.
    """

    URLS = {
        "get_submission": "/xqueue/get_submission/",
        "get_queuelen": "/xqueue/get_queuelen/",
        "login": "/xqueue/login/",
        "put_result": "/xqueue/put_result/",
    }

    def __init__(self, queue_name, url, username, password, timeout=30):
        self.queue_name = queue_name
        self.url = url
        self.username = username
        self.password = password
        self.timeout = timeout

        self.session = requests.session()
        self.login()

    @statsd.timed('xqueue.XQueueClient.login')
    def login(self):
        """ Login to xqueue. """
        login_url = urlparse.urljoin(self.url, self.URLS['login'])
        creds = {"username": self.username, "password": self.password}

        response = self.session.post(login_url, creds)
        response.raise_for_status()

        return self._parse_xreply(response.content)

    @statsd.timed('xqueue.XQueueClient.get_submission')
    def get_submission(self):
        """ Get a single submission from xqueue. """
        time_start = time.time()

        if self.has_submissions():
            url = urlparse.urljoin(self.url, self.URLS['get_submission'])

            try:
                success, response = self._http_get(url,
                                                   {'queue_name': self.queue_name})
            except Exception as err:
                log.error(err)
                return False

            submission = self._parse_submission(response)
            if submission:
                time_stop = time.time()
                elapsed_time = (time_stop - time_start)*1000.0
                log.info("> Fetched submission from queue \"%s\" in %0.3fms",
                         self.queue_name, elapsed_time)
                return submission

        return False

    def has_submissions(self):
        """ Determine whether or not there is a submission in the queue. """
        success, response = self.get_queue_length()
        return success and response > 0

    def get_queue_length(self):
        """ Get a single submission from xqueue. """
        url = urlparse.urljoin(self.url, self.URLS['get_queuelen'])

        try:
            success, response = self._http_get(url,
                                               {'queue_name': self.queue_name})
        except Exception as err:
            return False, "Error getting response: {0}".format(err)

        return success, response

    @statsd.timed('xqueue.XQueueClient.put_result')
    def put_result(self, submission, grader_reply):
        """ Post the results from the grader back to xqueue. """
        time_start = time.time()
        url = urlparse.urljoin(self.url, self.URLS['put_result'])

        header = {
            "submission_id": submission["id"],
            "submission_key": submission["key"]
        }

        response = {
            "xqueue_header": json.dumps(header),
            "xqueue_body": json.dumps(grader_reply)
        }
        success, msg = self._http_post(url, response)

        time_stop = time.time()
        elapsed_time = (time_stop - time_start)*1000.0
        log.info("> Put result to queue \"%s\" in %0.3fms",
                 self.queue_name, elapsed_time)
        return success, msg

    def _parse_submission(self, submission):
        """ Parse submission headers, student response and grader payload from submission """
        try:
            xobject = json.loads(submission)
            header = json.loads(xobject["xqueue_header"])
            body = json.loads(xobject["xqueue_body"])

            response = {
                "id": header["submission_id"],
                "key": header["submission_key"],
                "student_response": body["student_response"],
                "grader_payload": json.loads(body["grader_payload"])
            }
        except ValueError:
            log.error("Unexpected reply from server: %s", submission)
            return False
        return response

    def _parse_xreply(self, xreply):
        """Parse the reply from xqueue.

        Messages are JSON-serialized dict:
        {
            "return_code": 0 (success), 1 (fail)
            "content": Message from xqueue (string)
        }

        """
        try:
            xreply = json.loads(xreply)
        except ValueError:
            error_message = "Could not parse xreply."
            log.error(error_message)
            return (False, error_message)

        # This is to correctly parse xserver replies and internal
        # success/failure messages
        if 'return_code' in xreply:
            return_code = (xreply['return_code'] == 0)
            content = xreply['content']
        elif 'success' in xreply:
            return_code = xreply['success']
            content = xreply
        else:
            return False, "Cannot find a valid success or return code."

        if return_code not in [True, False]:
            return False, 'Invalid return code.'

        return return_code, content

    def _http_get(self, url, data=None):
        """ Helper for making HTTP GET requests to xqueue.

        Arguments:
            url -- url to send request to
            data -- optional dictionary to send

        Returns (success, response), where:
            success -- Flag indicating succesful exchange. (Boolean)
            response -- A parsed xqueue reply. (Dict)

        """
        if data is None:
            data = {}
        try:
            r = self.session.get(url, params=data)
        except requests.exceptions.ConnectionError:
            error_message = "Cannot connect to server."
            log.error(error_message)
            return False, error_message

        if r.status_code == 500 and url.endswith("/"):
            r = self.session.get(url[:-1], params=data)

        if r.status_code == 403:
            self.login()
            r = self.session.get(url, params=data)

        if r.status_code not in [200]:
            return False, 'Unexpected HTTP status code [%d]' % r.status_code
        if hasattr(r, "text"):
            text = r.text
        elif hasattr(r, "content"):
            text = r.content
        else:
            error_message = "Could not get response from http object."
            log.exception(error_message)
            return False, error_message
        return self._parse_xreply(text)

    def _http_post(self, url, data):
        """ Helper for making HTTP POST requests to xqueue.

        Takes following arguments:
            url -- url to send request to
            data -- dictionary of data to post

        Returns (success, msg), where:
            success -- Flag indicating successful exchange. (Boolean)
            msg -- Controller reply when successful. (str)

        """
        try:
            r = self.session.post(url, data=data, timeout=self.timeout,
                                  verify=False)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout):
            error_message = "Could not connect to server at %s in timeout=%f" % (url, self.timeout)
            log.error(error_message)
            return False, error_message

        if r.status_code == 500 and url.endswith("/"):
            r = self.session.post(url[:-1], data=data, timeout=self.timeout,
                                  verify=False)

        if r.status_code == 403:
            self.login()
            r = self.session.post(url, data=data, timeout=self.timeout,
                                  verify=False)

        if r.status_code not in [200]:
            error_message = "Server %s returned status_code=%d' % (url, r.status_code)"
            log.error(error_message)
            return False, error_message

        if hasattr(r, "text"):
            text = r.text
        elif hasattr(r, "content"):
            text = r.content
        else:
            error_message = "Could not get response from http object."
            log.exception(error_message)
            return False, error_message

        return True, text
