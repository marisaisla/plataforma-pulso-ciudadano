import unittest
from unittest.mock import patch
from decimal import Decimal
from types import SimpleNamespace

from services import database
from services.postgres_backend import Row, translate, row_factory


class PostgreSQLAdapterTests(unittest.TestCase):
    def test_placeholders_do_not_change_literals_identifiers_or_comments(self):
        sql = "SELECT ?, '? 100% CURRENT_TIMESTAMP', \"question?\" -- ?\n/* ? */ WHERE x LIKE 'OpenAI%'"
        converted = translate(sql)
        self.assertEqual(converted.count('%s'), 1)
        self.assertIn("'? 100%% CURRENT_TIMESTAMP'", converted)
        self.assertIn('"question?" -- ?\n/* ? */', converted)
        self.assertIn("'OpenAI%%'", converted)

    def test_ignore_timestamp_and_aggregation(self):
        self.assertEqual(translate('INSERT OR IGNORE INTO x VALUES (?);'),
                         'INSERT INTO x VALUES (%s) ON CONFLICT DO NOTHING')
        self.assertIn('STRING_AGG', translate("SELECT GROUP_CONCAT(name, ', ') FROM x"))
        self.assertIn("AT TIME ZONE 'UTC'", translate('UPDATE x SET created_at=CURRENT_TIMESTAMP'))
        for sql in ('PRAGMA table_info(x)', 'INSERT OR REPLACE INTO x VALUES (?)'):
            with self.assertRaises(ValueError):
                translate(sql)

    def test_rows_support_mapping_positions_unpacking_and_json_numbers(self):
        row = Row((1, 'María'), ('id', 'name'))
        self.assertEqual(row[0], row['id'])
        self.assertEqual(dict(row), {'id': 1, 'name': 'María'})
        self.assertEqual(tuple(row), (1, 'María'))
        make = row_factory(SimpleNamespace(description=[SimpleNamespace(name='sum'), SimpleNamespace(name='avg')]))
        row = make([Decimal('9007199254740993'), Decimal('1.25')])
        self.assertEqual(row[0], 9007199254740993)
        self.assertIsInstance(row[0], int)
        self.assertIsInstance(row[1], float)

    def test_invalid_backend_never_falls_back_to_sqlite(self):
        with patch.object(database, 'get_setting', return_value='postgress'), patch.object(database.sqlite3, 'connect') as sqlite:
            with self.assertRaises(ValueError):
                database.connection()
            sqlite.assert_not_called()


if __name__ == '__main__':
    unittest.main()
