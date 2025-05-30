import ollama
import time
import numpy as np
import tiktoken

class WorkMemory:
    def __init__(self):
        self.llm = 'gpt-4o'
        self.maxtoken = 3.2e4
        self.beta = 0.5
        self.alpha = 0.5
        self.embedding_model = 'nomic-embed-text'
        self.embedding_size = 768,
        self.memory = []
        self.tokens = 0
        self.tokenizer = tiktoken.encoding_for_model(self.llm)

    def drop(self, query):
        now_time = time.time()
        query_vector = ollama.embeddings(
            model=self.embedding_model,
            prompt=query,
        ).embedding

        cos_sim = [np.dot(query_vector, m['vector']) / (np.linalg.norm(query_vector) * np.linalg.norm(m['vector'])) for m in self.memory]
        time_gap = [(now_time - m['insert_time']) / (now_time - min([m['insert_time'] for m in self.memory])) for m in self.memory]
        value = [(c ** self.alpha) * (t ** self.beta) for c, t in zip(cos_sim, time_gap)]
        min_index, min_value = min(enumerate(value), key=lambda x: x[1])
        drop_token = self.tokenizer.encode(self.memory[min_index]['content'])
        drop_content = self.memory.pop(min_index)
        return drop_content, drop_token

    def insert(self, new_memory):
        tokens = len(self.tokenizer.encode(new_memory))
        drop_list = []
        while self.tokens + tokens > self.maxtoken:
            drop_content, drop_token = self.drop(new_memory)
            drop_list.append(drop_content)
            self.tokens -= drop_token
        vector = ollama.embeddings(
            model=self.embedding_model,
            prompt=new_memory,
        )
        self.memory.append({'content': new_memory, 'vector': vector, 'insert_time': time.time()})
        return drop_list
