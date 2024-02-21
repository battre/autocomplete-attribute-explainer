from contextlib import contextmanager
import time


@contextmanager
def print_time_on_exit(task_name):
  start_time = time.time()
  try:
    yield
  finally:
    end_time = time.time()
    execution_time = end_time - start_time
    print(f"{task_name} execution time: {execution_time*1000:.3f} ms")
