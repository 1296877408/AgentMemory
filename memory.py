import long_memory
import work_memory
import SensoryMemory

class Memory:
    def __init__(self):
        self.wait_to_update = 0
        self.max_loop = 10
        self.update_agent = None
        self.retrieve_agent = None
        self.sensory_memory = SensoryMemory.SensoryMemory()
        self.long_memory = long_memory.LongTermMemory()
        self.work_memory = work_memory.WorkMemory()

    def read(self):
        #读取工作记忆
        return self.work_memory.memory


    def search(self, query):
        #从长期记忆中查找信息
        if self.wait_to_update > 12.8e3 or self.max_loop <= 0:
            self.long_memory.update()
            self.wait_to_update = 0
            self.max_loop = 10
        memory = self.long_memory.search(query)
        drop_list = self.work_memory.insert(memory)
        self.long_memory.temporary_longterm_memory.append(drop_list)
        return self.work_memory.memory

    def add(self, content):
        #更新工作记忆
        if self.wait_to_update > 12.8e3 or self.max_loop <= 0:
            self.long_memory.update()
            self.wait_to_update = 0
            self.max_loop = 10
        drop_list = self.work_memory.insert(content)
        self.long_memory.temporary_longterm_memory.append(drop_list)

    def insert(self, content):
        self.long_memory.insert(content)

