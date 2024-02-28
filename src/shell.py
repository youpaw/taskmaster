from multiprocessing import Queue


class Shell:
    def __init__(self):
        pass

    @staticmethod
    def read(queue: Queue):
        while True:
            try:
                command = input()
                queue.put(command)
            except EOFError as exc:
                print(exc)
