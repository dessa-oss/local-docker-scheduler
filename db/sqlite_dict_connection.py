from sqlitedict import SqliteDict
import atexit

def _close_sqlite_dict_connection(con):
    con.commit()
    con.close()


def connect(location):
    con = SqliteDict(location, autocommit=True)
    atexit.register(_close_sqlite_dict_connection, con)
    return con