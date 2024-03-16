from misc.colored_prints import print_green


def timing_decorator(func):
    def wrapper(*args, **kwargs):
        import time
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print_green(f"{func.__name__} running time: {end_time - start_time} s")
        return result
    return wrapper
