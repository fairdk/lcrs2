import gobject

def idle_add_decorator(func):
    def callback(*args):
        gobject.idle_add(func, *args)
    return callback
    