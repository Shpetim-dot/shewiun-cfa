from app.db import CompatRow, PostgresConnection


class FakeCursor:
    def __init__(self, query, params):
        self.query = query
        self.params = params


class FakeConnection:
    def __init__(self):
        self.last = None

    def execute(self, query, params=None):
        self.last = FakeCursor(query, params)
        return self.last


def test_postgres_adapter_translates_positional_and_named_parameters():
    raw = FakeConnection()
    db = PostgresConnection(raw)
    db.execute("SELECT * FROM projects WHERE id=? AND status=?", ("id-1", "Active"))
    assert raw.last.query == "SELECT * FROM projects WHERE id=%s AND status=%s"
    assert raw.last.params == ("id-1", "Active")
    db.execute("INSERT INTO projects VALUES (:id, :name)", {"id": "1", "name": "Demo"})
    assert raw.last.query == "INSERT INTO projects VALUES (%(id)s, %(name)s)"


def test_postgres_row_supports_mapping_and_sqlite_style_indexing():
    row = CompatRow(id="abc", name="Shewiun")
    assert row["id"] == "abc"
    assert row[0] == "abc"
    assert row[1] == "Shewiun"
