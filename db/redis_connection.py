import redis
from pickle import loads, dumps


class RedisDict:
    def __init__(self, key, host, port, db=0):
        self._redis = redis.StrictRedis(host, port, db)
        self._key = key

    def __getitem__(self, field):
        response = self._redis.hget(self._key, dumps(field))
        if response is None:
            raise IndexError
        return loads(response)

    def __setitem__(self, field, value):
        return self._redis.hset(self._key, dumps(field), dumps(value))

    def items(self):
        return [(loads(field), loads(value)) for field, value in self._redis.hgetall(self._key).items()]

    def keys(self):
        return [loads(field) for field in self._redis.hkeys(self._key)]

    def __delitem__(self, field):
        return self._redis.hdel(self._key, field)


class RedisList:
    def __init__(self, key, host, port, db=0):
        self._redis = redis.StrictRedis(host, port, db)
        self._key = key

    def __getitem__(self, index):
        response = self._redis.lindex(self._key, index)
        if response is None:
            raise IndexError
        return loads(response)

    def __setitem__(self, index, value):
        return self._redis.lset(self._key, index, dumps(value))

    def __delitem__(self, index):
        return self._redis.lrem(self._key, 1, self[index])

    def insert(self, index, value):
        return self._redis.linsert(self._key, "before", self[index], dumps(value))

    def append(self, value):
        return self._redis.rpush(self._key, dumps(value))

    def pop(self, index=-1):
        if index == -1:
            response = self._redis.rpop(self._key)
            if response is None:
                raise IndexError
            return loads(response)
        elif index == 0:
            response = self._redis.lpop(self._key)
            if response is None:
                raise IndexError
            return loads(response)
        else:
            response = self[index]
            del self[index]
            return response

    def reposition(self, original_position, new_position):
        temp = self[original_position]
        del self[original_position]
        try:
            self.insert(new_position, temp)
        except IndexError:
            self.insert(original_position, temp)
            raise
