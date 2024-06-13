# TODO: File for optimal storage
import sqlite3


class OptimalRecipeStorage:
    db: sqlite3.Connection
    db_location: str = "cache/optimals.db"
    closed: bool = False

    def __init__(self):
        self.db = sqlite3.connect(self.db_location, isolation_level=None)
        self.db.execute("pragma journal_mode=wal")
        self.db.execute("CREATE TABLE IF NOT EXISTS optimals (id INTEGER PRIMARY KEY, name TEXT UNIQUE, optimal TEXT)")

    def get_optimal(self, name: str) -> str:
        cursor = self.db.cursor()
        cursor.execute("SELECT optimal FROM optimals WHERE name = ?", (name,))
        result = cursor.fetchone()
        if result is None:
            return ""
        return result[0]

    def get_all_optimals(self) -> list[tuple[int, str, str]]:
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM optimals")
        return cursor.fetchall()

    def add_optimal(self, name: str, optimal: str):
        cursor = self.db.cursor()
        if self.get_optimal(name) == "":
            cursor.execute("INSERT INTO optimals (name, optimal) VALUES (?, ?)", (name, optimal))
        else:
            cursor.execute("update optimals set optimal = optimal || ? where name = ?", (optimal, name))

    # def remove_optimal(self, name: str):
    #     cursor = self.db.cursor()
    #     cursor.execute("DELETE FROM optimals WHERE name = ?", (name,))

    def clear(self):
        cursor = self.db.cursor()
        cursor.execute("DELETE FROM optimals")

    def close(self):
        if not self.closed:
            self.db.close()
            self.closed = True


def main():
    optimal = OptimalRecipeStorage()
    # optimal.clear()
    # optimal.add_optimal("test", "test=test=test==")
    # print(optimal.get_optimal("test"))
    optimal.close()


if __name__ == "__main__":
    main()
