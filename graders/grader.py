import csv
import hashlib
import logging
import MySQLdb
import os
import sqlite3

from StringIO import StringIO

from boto.s3.connection import S3Connection
from boto.s3.key import Key

from .exceptions import InvalidQuery, InvalidGrader

log = logging.getLogger(__file__)


def make_hashkey(seed):
    """
    Generate a string key by hashing
    """
    h = hashlib.md5()
    h.update(str(seed))
    return h.hexdigest()


class BaseGrader(object):
    """ Base class for edX External Graders """

    def grade(self):
        """
        Abstract - subclasses must implement
        """
        raise NotImplementedError


class S3UploaderMixin(object):
    DEFAULT_S3_FILENAME = 'results.csv'

    def __init__(self, s3_bucket, s3_prefix, aws_access_key, aws_secret_key, *args, **kwargs):
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix
        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key

    def upload(self, contents, path, name):
        """Upload submission results to S3

        TODO:
            - Use query_auth=False for `generate_url` if bucket is public

        """
        s3 = S3Connection(self.aws_access_key, self.aws_secret_key)
        bucket = s3.get_bucket(self.s3_bucket)

        keyname = "{prefix}/{path}/{name}".format(prefix=self.s3_prefix,
                                                  path=path, name=name)
        key = Key(bucket, keyname)
        key.set_contents_from_string(contents, replace=True)
        s3_url = key.generate_url(60*60*24)

        return s3_url


class MySQLGrader(S3UploaderMixin, BaseGrader):
    """ External grader for SQL statements (MySQL Backend)"""

    def __init__(self, database, host, user, passwd, port=3306, *args, **kwargs):
        try:
            self.db = MySQLdb.connect(host, user, passwd, database, port)
        except MySQLdb.OperationalError as e:
            raise InvalidGrader(e)

        super(MySQLGrader, self).__init__(*args, **kwargs)

    def __del__(self):
        if hasattr(self, 'db') and self.db:
            self.db.close()

    def grade(self, submission):
        """
        Execute both the student and teacher responses, comparing
        results to determine grade.
        """
        student_response = submission.get('student_response')
        grader_payload = submission.get('grader_payload')
        response = {
            "correct": False,
            "score": 0,
            "grader_id": str(self)
        }

        try:
            student_cols, student_rows = self.execute_query(student_response)
        except InvalidQuery as e:
            response["msg"] = """
<div class="error">
    <p>Could not execute query: <code>{query}</code></p>
    <h4>Error:</h4>
    <pre><code>{error}</code></pre>
</div>
            """.format(query=student_response, error=str(e)).strip(' \t\n\r')
            return response

        grader_answer = grader_payload.get('answer')
        if grader_answer:
            try:
                grader_cols, grader_rows = self.execute_query(grader_answer)
            except InvalidQuery as e:
                response["msg"] = """
<div class="error">
    <p><strong>Invalid grader query</strong>: <code>{query}</code></p>
    <p>Please report this issue to the course staff.</p>
    <h4>Error:</h4>
    <pre><code>{error}</code></pre>
</div>
                """.format(query=grader_answer, error=str(e)).strip(' \t\n\r')
                return response

            if student_rows == grader_rows:

                html = self.to_html(grader_rows, grader_cols)

                response["correct"] = True
                response["score"] = 1
                response["msg"] = """
<div class="correct">
    <h3>Query results:</h3>
    <pre><code>{results}</code></pre>
</div>
                """.format(results=html).strip(' \t\n\r')
            else:
                expected = self.to_html(grader_rows, grader_cols)
                actual = self.to_html(student_rows, student_cols)

                response["msg"] = """
<div class="error">
    <h3>Expected Results</h3>
    <pre><code class="expected">{expected}</code></pre>
    <h3>Your Results</h3>
    <pre><code class="actual">{actual}</code></pre>
</div>
                """.format(expected=expected, actual=actual).strip(' \t\n\r')

        else:

            html = self.to_html(student_rows, student_cols)

            response["correct"] = True
            response["msg"] = """
<div class="sandbox">
    <h3>Query Results</h3>
    <pre><code>{results}</code></pre>
</div>
            """.format(results=html).strip(' \t\n\r')

        # Upload correct response results to S3
        if response["correct"]:
            csv_results = self.to_csv(student_rows, student_cols)

            s3_path = make_hashkey(submission)
            s3_name = grader_payload.get('filename', self.DEFAULT_S3_FILENAME)
            s3_url = self.upload(csv_results, s3_path, s3_name)

            # Append download link
            response["msg"] += "<p>Download CSV: <a href=\"{s3_url}\">{s3_name}</a></p>".format(s3_url=s3_url, s3_name=s3_name)

        #
        # Quick and dirty kludge to prevent breaking our response.
        #
        # The LMS runs grader messages through lxml.etree.fromstring which
        # fails with invalid XML, resulting in:
        #
        #   "Invalid grader reply. Please contact the course staff."
        #
        response["msg"] = response["msg"].replace("&", "&amp;")
        response["msg"] = "<div class=\"resulst\">" + response["msg"] + "</div>"

        return response

    def execute_query(self, stmt):
        cursor = self.db.cursor()
        try:
            cursor.execute(stmt)
            rows = cursor.fetchall()
            cols = [str(col[0]) for col in cursor.description]
        except (MySQLdb.OperationalError, MySQLdb.Warning, MySQLdb.Error) as e:
            msg = e.args[1]
            code = e.args[0]
            raise InvalidQuery("MySQL Error {}: {}".format(code, msg))
        return cols, rows

    def to_csv(self, results, header=None):
        """Convert grader results to CSV"""
        sio = StringIO()
        writer = csv.writer(sio)

        if header:
            writer.writerow(header)

        for row in results:
            writer.writerow(row)

        csv_results = sio.getvalue()
        sio.close()
        return csv_results

    def to_html(self, results, header=None):
        if len(results) < 1:
            return ''

        html = "<table><thead>"
        html += "<tr><th>{}</th></tr>".format("</th><th>".join(header))
        html += "</thead><tbody>"

        for row in results:
            html += "<tr><td>{}</td></tr>".format(
                    "</td><td>".join(str(col) for col in row))

        html += "</tbody></table>"
        return html


class SQLiteGrader(BaseGrader):
    """ External grader for SQL statements (SQLite Backend)"""

    def __init__(self, database, data_dir='', *args, **kwargs):
        db_path = os.path.join(data_dir, database)
        if not os.path.exists(db_path):
            raise InvalidGrader("Database does not exist: {}".format(db_path))
        try:
            self.db = sqlite3.connect(db_path)
        except sqlite3.OperationalError as e:
            raise InvalidGrader(e)

        super(SQLiteGrader, self).__init__(*args, **kwargs)

    def __del__(self):
        if hasattr(self, 'db') and self.db:
            self.db.close()

    def grade(self, submission):
        """
        Execute both the student and teacher responses, comparing
        results to determine grade.
        """
        student_response = submission['student_response']
        grader_payload = submission['grader_payload']
        response = {
            "correct": False,
            "score": 0,
            "grader_id": str(self)
        }

        try:
            student_cols, student_rows = self.execute_query(student_response)
        except InvalidQuery as e:
            response["msg"] = """
<div class="error"><p><strong>Bad student query</strong>: "{query}"</p>
<p>Error message:</p> <code>{error}</code></div>
            """.format(query=student_response, error=e).strip(' \t\n\r')
            return response

        grader_answer = grader_payload['answer']
        try:
            grader_cols, grader_rows = self.execute_query(grader_answer)
        except InvalidQuery as e:
            response["msg"] = """
<div class="error"><p><strong>Bad teacher query</strong>: "{query}"</p>
<p>Error message:</p> <code>{error}</code></div>
            """.format(query=grader_answer, error=e).strip(' \t\n\r')
            return response

        if student_rows == grader_rows:
            formatted_results = self._format_results(grader_cols, grader_rows)
            response["correct"] = True
            response["score"] = 1
            response["msg"] = """
<div class="correct"><h3>Query results:</h3><code>{results}</code></div>
            """.format(results=formatted_results).strip(' \t\n\r')
        else:
            expected = self._format_results(grader_cols, grader_rows)
            actual = self._format_results(student_cols, student_rows)
            response["msg"] = """
<div class="error">
    <h3>Expected Results</h3>
    <code class="expected">{expected}</code>
    <h3>Your Results</h3>
    <code class="actual">{actual}</code>
</div>
            """.format(expected=expected, actual=actual).strip(' \t\n\r')

        return response

    def execute_query(self, stmt):
        cursor = self.db.cursor()
        try:
            cursor.execute(stmt)
            rows = cursor.fetchall()
            cols = [str(col[0]) for col in cursor.description]
        except (sqlite3.OperationalError, sqlite3.Warning) as e:
            raise InvalidQuery(e)
        return cols, rows

    def _format_results(self, cols, rows):
        if len(rows) < 1:
            return ''

        formatted = "<table style=\"max-width: 100%;\">"
        formatted += "<tr><th>{}</th></tr>".format("</th><th>".join(cols))

        for row in rows:
            formatted += "<tr><td>{}</td></tr>".format(
                         "</td><td>".join(str(col) for col in row))
        formatted += "</table>"
        return formatted
