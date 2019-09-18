"""
Copyright (C) DeepLearning Financial Technologies Inc. - All Rights Reserved
Unauthorized copying, distribution, reproduction, publication, use of this file, via any medium is strictly prohibited
Proprietary and confidential
Written by Eric lee <e.lee@dessa.com>, 08 2019
"""


from sqlitedict import SqliteDict
import atexit


def _close_sqlite_dict_connection(con):
    con.commit()
    con.close()


def connect(location):
    con = SqliteDict(location, autocommit=True)
    atexit.register(_close_sqlite_dict_connection, con)
    return con