import csv
import hashlib
import logging
import MySQLdb
import os
import sqlite3
import time

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

    def sanitize_row_limit(self, limit):
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = None

        if limit < 1:
            limit = None

        return limit

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

    def to_html(self, results, header=None, row_limit=None):
        if len(results) < 1:
            return ''

        row_limit = self.sanitize_row_limit(row_limit)

        html = "<table><thead>"
        html += "<tr><th>{}</th></tr>".format("</th><th>".join(header))
        html += "</thead><tbody>"

        for idx, row in enumerate(results):
            if row_limit and idx >= row_limit:
                break
            html += "<tr><td>{}</td></tr>".format(
                    "</td><td>".join(str(col) for col in row))

        html += "</tbody></table>"

        return html

    def result_stats(self, displayed, total):
        return "<p>Showing %d of %s row%s.</p>" % (displayed, total,
                                                   "s"[total == 1:])


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
        try:
            s3 = S3Connection(self.aws_access_key, self.aws_secret_key)
            bucket = s3.create_bucket(self.s3_bucket)

            keyname = "{prefix}/{path}/{name}".format(prefix=self.s3_prefix,
                                                      path=path, name=name)
            key = Key(bucket, keyname)
            key.set_contents_from_string(contents, replace=True)
            s3_url = key.generate_url(60*60*24)
        except Exception as e:
            log.error("Error uploading results to S3: %s", e)
            s3_url = False

        return s3_url


class SQLGrader(S3UploaderMixin, BaseGrader):
        def __del__(self):
            if hasattr(self, 'db') and self.db:
                self.db.close()

        def grade(self, submission):
            """
            Execute both the student and teacher responses, comparing
            results to determine grade.
            """
            time_start = time.time()

            student_response = submission.get('student_response')
            grader_payload = submission.get('grader_payload')

            row_limit = grader_payload.get("row_limit", None)
            row_limit = self.sanitize_row_limit(row_limit)

            response = {
                "correct": False,
                "score": 0,
                "grader_id": str(self)
            }

            try:
                student_cols, student_rows = self.execute_query(student_response)
                student_rows_found = len(student_rows)
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
                    grader_rows_found = len(grader_rows)

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

                    html = self.to_html(student_rows, student_cols, row_limit)

                    # Row count stats notice
                    rows_displayed = row_limit or student_rows_found
                    student_stats = self.result_stats(rows_displayed,
                                                      student_rows_found)

                    response["correct"] = True
                    response["score"] = 1
                    response["msg"] = """
    <div class="correct">
        <h3>Query results:</h3>
        <pre><code>{results}</code></pre>
        {stats}
    </div>
                    """.format(results=html, stats=student_stats) \
                       .strip(' \t\n\r')
                else:
                    expected = self.to_html(grader_rows,
                                            grader_cols,
                                            row_limit)
                    actual = self.to_html(student_rows,
                                          student_cols,
                                          row_limit)

                    # Row count stats notice
                    grader_rows_displayed = row_limit or grader_rows_found
                    student_rows_displayed = row_limit or student_rows_found
                    grader_stats = self.result_stats(grader_rows_displayed,
                                                     grader_rows_found)
                    student_stats = self.result_stats(student_rows_displayed,
                                                      student_rows_found)

                    response["msg"] = """
    <div class="error">
        <h3>Expected Results</h3>
        <pre><code class="expected">{expected}</code></pre>
        {grader_stats}
        <h3>Your Results</h3>
        <pre><code class="actual">{actual}</code></pre>
        {student_stats}
    </div>
                    """.format(expected=expected,
                               actual=actual,
                               grader_stats=grader_stats,
                               student_stats=student_stats) \
                       .strip(' \t\n\r')

            else:

                html = self.to_html(student_rows, student_cols, row_limit)
                student_rows_displayed = row_limit or student_rows_found
                stats = self.result_stats(student_rows_displayed,
                                          student_rows_found)

                response["correct"] = True
                response["msg"] = """
    <div class="sandbox">
        <h3>Query Results</h3>
        <pre><code>{results}</code></pre>
        {stats}
    </div>
                """.format(results=html, stats=stats).strip(' \t\n\r')

            # Upload student results to S3
            if student_rows:
                csv_results = self.to_csv(student_rows, student_cols)

                s3_path = make_hashkey((submission["id"], submission["key"]))
                s3_name = grader_payload.get('filename', self.DEFAULT_S3_FILENAME)
                s3_url = self.upload(csv_results, s3_path, s3_name)

                if s3_url:
                    download_link = """
    <p>Download your full results as CSV: <a href=\"{s3_url}\">{s3_name}</a></p>
                    """.format(s3_url=s3_url, s3_name=s3_name).strip(" \t\n\r")
                else:
                    download_link = "<p>Could not upload results file. Please contact course staff.</p>"

                response["msg"] += download_link

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

            time_stop = time.time()
            elapsed_time = (time_stop - time_start)*1000.0
            log.info("%s - Graded submission \"%s\" in %0.3fms",
                     type(self).__name__, submission["id"], elapsed_time)

            return response


class MySQLGrader(SQLGrader):
    """ External grader for SQL statements (MySQL Backend)"""

    def __init__(self, database, host, user, passwd, port=3306, *args, **kwargs):
        try:
            self.db = MySQLdb.connect(host, user, passwd, database, port)
        except MySQLdb.OperationalError as e:
            raise InvalidGrader(e)

        super(MySQLGrader, self).__init__(*args, **kwargs)

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


class SQLiteGrader(SQLGrader):
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

    def execute_query(self, stmt):
        cursor = self.db.cursor()
        try:
            cursor.execute(stmt)
            rows = cursor.fetchall()
            cols = [str(col[0]) for col in cursor.description]
        except (sqlite3.OperationalError, sqlite3.Warning) as e:
            raise InvalidQuery(e)
        return cols, rows
