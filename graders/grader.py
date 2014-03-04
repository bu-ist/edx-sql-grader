import logging
import MySQLdb
import os
import sqlite3

from .exceptions import InvalidQuery, InvalidGrader

log = logging.getLogger(__file__)


class BaseGrader(object):
    """ Base class for edX External Graders """

    def grade(self):
        """
        Abstract - subclasses must implement
        """
        raise NotImplementedError


class MySQLGrader(BaseGrader):
    """ External grader for SQL statements (MySQL Backend)"""

    def __init__(self, db, host, user, passwd, port=3306, *args, **kwargs):
        try:
            self.db = MySQLdb.connect(host, user, passwd, db, port)
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
                results = self._format_results(grader_cols, grader_rows)

                response["correct"] = True
                response["score"] = 1
                response["msg"] = """
<div class="correct">
    <h3>Query results:</h3>
    <pre><code>{results}</code></pre>
</div>
                """.format(results=results).strip(' \t\n\r')
            else:
                expected = self._format_results(grader_cols, grader_rows)
                actual = self._format_results(student_cols, student_rows)

                response["msg"] = """
<div class="error">
    <h3>Expected Results</h3>
    <pre><code class="expected">{expected}</code></pre>
    <h3>Your Results</h3>
    <pre><code class="actual">{actual}</code></pre>
</div>
                """.format(expected=expected, actual=actual).strip(' \t\n\r')

        else:
            results = self._format_results(student_cols, student_rows)

            response["correct"] = True
            response["msg"] = """
<div class="sandbox">
    <h3>Query Results</h3>
    <pre><code>{results}</code></pre>
</div>
            """.format(results=results).strip(' \t\n\r')

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

    def _format_results(self, cols, rows):
        if len(rows) < 1:
            return ''

        formatted = "<table><thead>"
        formatted += "<tr><th>{}</th></tr>".format("</th><th>".join(cols))
        formatted += "</thead><tbody>"

        for row in rows:
            formatted += "<tr><td>{}</td></tr>".format(
                         "</td><td>".join(str(col) for col in row))
        formatted += "</tbody></table>"
        return formatted


class SQLiteGrader(BaseGrader):
    """ External grader for SQL statements (SQLite Backend)"""

    def __init__(self, db, data_dir='', *args, **kwargs):
        db_path = os.path.join(data_dir, db)
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
