import ollama
import openai
from py2neo import Graph, Node, Relationship
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance,PointStruct
import hashlib
import tiktoken
import json
from dotenv import load_dotenv
import time

load_dotenv()
class LongTermMemory:
    def __init__(self):
        self.graphDB = Graph(
            "bolt://localhost:7687",
            auth=("neo4j", "aA007812"),
        )
        self.vectorDB = QdrantClient(
            host="localhost",
            port=6333
        )
        with open('./mem_num.json', 'r', encoding='utf-8') as f:
            self.mem_num = json.load(f)[0]
        with open('./extract_prompt.txt', 'r', encoding='utf-8') as f:
            self.extract_prompt = f.read()
        with open('./previous_chunk.txt', 'r', encoding='utf-8') as f:
            self.previous_chunk = f.readlines()
        self.text_collection = "text_collection"
        self.community_collection = "community_collection"
        self.entity_collection = "entity_collection"
        self.relationship_collection = "relationship_collection"
        self.temporary_longterm_memory = []
        self.embedding_size = 768
        self.embedding_model = 'nomic-embed-text'
        self.llm = 'gpt-4o'
        self.llm_client = openai.OpenAI()
        self.tokenizer = tiktoken.encoding_for_model(self.llm)

    def search(self, query):
        query_embedding = ollama.embeddings(
            model_name=self.embedding_model,
            prompt=query,
        ).embedding

        community_info = self.vectorDB.search(
            collection_name=self.community_collection,
            query_embedding=query_embedding,
            limit=10,
        )

        community_info = [info for info in community_info if info.score > 0.8]

        if len(community_info) > 5:
            for info in community_info:
                payload = info.payload
                text = payload['text']
                entity = payload['entity']
                relationship = payload['relationship']
                text_info = [self.vectorDB.retrieve(collection_name=self.text_collection, ids=[ids]) for ids in text]
                entity_info = [self.graphDB.nodes.match(ids=ids).all()[0]['description'] for ids in entity]
                relationship_info = [self.graphDB.relationships.match(ids=ids).all()[0]['description'] for ids in relationship]

                result_json = {
                    "text": text_info,
                    "entity": entity_info,
                    "relationship": relationship_info,
                }

                return result_json


        else:
            entity_info = self.vectorDB.search(
                collection_name=self.entity_collection,
                query_vector=query_embedding,
                limit = 20,
                )
            relationship_info = self.vectorDB.search(
                collection_name=self.relationship_collection,
                query_vector=query_embedding,
                limit = 20,
            )

            return 1



    def insert(self, content:str):
        #长文本分块
        max_tokens = 512
        tokens = self.tokenizer.encode(content)
        start = 0
        while start < len(tokens):
            chunk = self.tokenizer.decode(tokens[start:start + max_tokens])
            chunk_ids = hashlib.md5(chunk.encode()).hexdigest()
            if chunk_ids not in self.previous_chunk:
                #如果文本不存在才在文本库中添加
                self.mem_num['chunk_num'] += 1
                self.previous_chunk.append(chunk_ids)
                chunk_vector = ollama.embeddings(
                    model=self.embedding_model,
                    prompt=chunk
                ).embedding
                chunk_point = [
                    PointStruct(
                        id=chunk_ids,
                        vector=chunk_vector,
                    )
                ]
                self.vectorDB.upsert(
                    collection_name=self.text_collection,
                    points=chunk_point,
                )
                start += max_tokens
                #提取文本中的entity和relationship
                response = self.llm_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": self.extract_prompt},
                        {"role": "user", "content": chunk}
                    ]
                )
                entity_relationship = response.choices[0].message.content
                json_pos = entity_relationship.find('json')
                entity_relationship = json.loads(entity_relationship[json_pos+4:-4])
                entities = []
                for e in entity_relationship:
                    #在graphdb和vectordb中存储entity
                    if 'entity' in e:
                        self.mem_num['entity_num'] += 1
                        attribute = {k: v for k, v in e.items() if k != 'entity'}
                        attribute['text'] = chunk_ids
                        entity_vector = ollama.embeddings(
                            model=self.embedding_model,
                            prompt=e['description'],
                        ).embedding
                        entity_ids = hashlib.md5((chunk+e['description']).encode()).hexdigest()
                        attribute['ids'] = entity_ids
                        attribute['create_time'] =time.time()
                        attribute['used'] = 0
                        entity_point = [
                            PointStruct(
                                id = entity_ids,
                                vector = entity_vector,
                            )
                        ]
                        entity = Node(e['entity'], **attribute)
                        entities.append(entity)
                        self.vectorDB.upsert(
                            collection_name=self.entity_collection,
                            points=entity_point
                        )
                        self.graphDB.create(entity)
                    elif 'relationship' in e:
                        source_name = e['source']['name']
                        source_label = e['source']['type']
                        target_name = e['target']['name']
                        target_label = e['target']['type']
                        relationship = e['relationship']
                        source = [s for s in entities if s['name'] == source_name][0]
                        target = [t for t in entities if t['name'] == target_name][0]
                        attribute = {k:v for k, v in e.items() if k!='source' and k!='target' and k!='relationship'}
                        relationship_vector = ollama.embeddings(
                            model=self.embedding_model,
                            prompt=e['description'],
                        ).embedding
                        relationship_ids = hashlib.md5((chunk+e['description']).encode()).hexdigest()
                        relationship_point = [
                            PointStruct(
                                id = relationship_ids,
                                vector=relationship_vector,
                            )
                        ]
                        self.vectorDB.upsert(
                            collection_name=self.relationship_collection,
                            points=relationship_point
                        )
                        attribute['ids'] = relationship_ids
                        attribute['text'] = chunk_ids
                        attribute['create_time'] = time.time()
                        attribute['used'] = 0
                        rel = Relationship(source, relationship, target, **attribute)
                        self.graphDB.create(rel)


    def update(self):
        pass

m = LongTermMemory()
pass