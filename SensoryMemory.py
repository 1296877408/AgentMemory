from collections import deque

class SensoryMemory:
    def __init__(self):
        self.max_memory = 5
        self.memory = deque(maxlen=self.max_memory)

    def insert(self, query):
        self.memory.append({"query":query})