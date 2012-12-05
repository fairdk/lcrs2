import gobject

def idle_add_decorator(func):
    gobject.idle_add(func)
    