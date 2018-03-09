import gevent
import gevent.queue


class Actor:
    def __init__(self):
        self.__mailbox = gevent.queue.Queue()
        self.__proc = gevent.spawn(self.__proc)

    def __getattr__(self, name):
        def method(*arg, **kwargs):
            self.__mailbox.put((name, arg, kwargs))
        return method

    def __proc(self):
        while True:
            method, arg, kwargs = self.__mailbox.get()
            if method == 'stop':
                break
            obj_method = getattr(self.__obj, method)
            obj_method(*arg, **kwargs)


def spawn(klass, *args, **kwargs):
    actor = Actor()
    obj = klass(actor, *args, **kwargs)
    actor._Actor__obj = obj
    return actor


def wait_for(*actors):
    gevent.joinall([a._Actor__proc for a in actors])
