import logging
import os
import sqlite3

from .base import BaseGrader
from .exceptions import InvalidQuery, InvalidGrader

log = logging.getLogger(__file__)


class SQLiteGrader(BaseGrader):
    """ External grader for SQL statements (SQLite Backend)"""

    def __init__(self, db_name, data_dir='', *args, **kwargs):
        db_path = os.path.join(data_dir, db_name)
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
<div class="correct"><h3>Query results:</h3>{results}</div>
            """.format(results=formatted_results).strip(' \t\n\r')
        else:
            expected = self._format_results(grader_cols, grader_rows)
            actual = self._format_results(student_cols, student_rows)
            response["msg"] = """
<div class="error">
    <h3>Expected Results</h3>
    <div class="expected">{expected}</div>
    <h3>Your Results</h3>
    <div class="actual">{actual}</div>
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
