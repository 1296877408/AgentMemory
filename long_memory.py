import ollama
import openai
from py2neo import Graph, Node, Relationship, Node
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance,PointStruct
import hashlib
import tiktoken
import json
from dotenv import load_dotenv
import time
import configparser
import cypher

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
        self.ids = configparser.ConfigParser()

    def search(self, query):
        type = query['type']
        q = query['query']
        query_embedding = ollama.embeddings(
            model=self.embedding_model,
            prompt=q,
        ).embedding

        community_info = self.vectorDB.search(
            collection_name=self.community_collection,
            query_vector=query_embedding,
            limit=10,
        )

        community_info = [info for info in community_info if info.score > 0.8 and info.type == type]

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
            res = []
            entity_info = self.vectorDB.search(
                collection_name=self.entity_collection,
                query_vector=query_embedding,
                limit = 20,
                )
            entity = [self.graphDB.nodes.match().where(f'_.ids = {e.id}').all() for e in entity_info]
            res.extend([{"entity_name": e.name, "description": e.description} for e in entity])
            relationship_info = self.vectorDB.search(
                collection_name=self.relationship_collection,
                query_vector=query_embedding,
                limit = 20,
            )
            relationship = [self.graphDB.relationships.match().where(f"_.ids={r.id}").all() for r in relationship_info]
            res.extend([{"relationship":r.lables, "keyword":r.keyword,"description":r.description} for r in relationship])
            return res



    def insert(self, content:str):
        #长文本分块
        max_tokens = 512
        tokens = self.tokenizer.encode(content)
        start = 0
        while start < len(tokens):
            chunk = self.tokenizer.decode(tokens[start:start + max_tokens])
            if len(self.vectorDB.search(collection_name=self.text_collection, query_vector=ollama.embeddings(model=self.embedding_model, prompt=chunk).embedding, score_threshold=0.95)):
                #如果文本不存在才在文本库中添加
                chunk_ids = self.mem_num['chunk_num']
                self.mem_num['chunk_num'] += 1
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
                entity_relationship = self._extract_er(chunk)
                entity_relationship = json.loads(entity_relationship)
                exist_e, exist_r = self._get_exist_er(chunk)

                for info in entity_relationship:
                    if "entity" in info:
                        pass


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
                        attribute['create_time'] = time.time()
                        attribute['latest_update'] = time.time()
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
                        source = [s for s in entities if s['name'] == source_name and s['type'] == source_label][0]
                        target = [t for t in entities if t['name'] == target_name  and t['type'] == target_label][0]
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
        if len(self.temporary_longterm_memory):
            pass

    def _search_graphdb(self, query:str):
        community_resp = self._search_vectordb(collection_name=self.community_collection, query=query)
        community_resp = [resp for resp in community_resp if resp.score>=0.7]
        if len(community_resp):
            for c in community_resp:




                


    def _search_graphdb_by_id(self, ids:list):
        resp = self.graphDB.run(cypher=cypher.search_by_ids, ids=int)
        resp = list(resp)
        return resp

    def _insert_vectordb(self, collection_name:str, ids:int, text:str):
        if collection_name != self.text_collection and collection_name != self.entity_collection and collection_name != self.relationship_collection and collection_name != self.entity_collection:
            raise Exception("Unknown collection name")
        if self._is_exist_text(collection_name=collection_name, query=text):
            return
        else:
            point = self._create_point(ids=ids, text=text)
            self.vectorDB.upsert(
                collection_name=collection_name,
                points=[point],
            )
            return

    def _extract_er(self, query:str):
        response = self.llm_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": self.extract_prompt},
                {"role": "user", "content": query}
            ]
        )
        entity_relationship = response.choices[0].message.content
        return entity_relationship[7:-4]

    def _get_exist_er(self, query:str):
        extract_er = json.loads(self._extract_er(query))
        entity = [{'name': e["name"], 'type': e["entity"]} for e in extract_er if 'entity' in e]
        cursor_r = self.graphDB.run(cypher=cypher.search_exist_r, entity=entity)
        cursor_e = self.graphDB.run(cypher=cypher.search_exist_e, entity=entity)
        exist_r = list(cursor_r)
        exist_e = list(cursor_e)
        return exist_e, exist_r

    def _embedding(self, query:str):
        return ollama.embeddings(
            model=self.embedding_model,
            prompt=query,
        ).embedding

    def _create_point(self, ids:int, text:str):
        vector = self._embedding(text)
        return PointStruct(
            id=ids,
            vector=vector,
        )

    def _is_exist_text(self, collection_name:str, query:str):
        if collection_name != self.text_collection and collection_name != self.entity_collection and collection_name != self.relationship_collection and collection_name != self.entity_collection:
            raise Exception("Unknown collection name")
        vector = self._embedding(query)
        resp = self.vectorDB.search(collection_name=collection_name,query_vector=vector,score_threshold=0.9)
        if len(resp) == 0:
            return False
        else:
            return True

    def _search_vectordb_by_id(self, collection_name:str, ids:list[int]):
        if collection_name != self.text_collection and collection_name != self.entity_collection and collection_name != self.relationship_collection and collection_name != self.entity_collection:
            raise Exception("Unknown collection name")
        points = self.vectorDB.retrieve(collection_name=collection_name,ids=ids)
        return points


    def _search_vectordb(self, collection_name, query:str)->list:
        if collection_name != self.text_collection and collection_name != self.entity_collection and collection_name != self.relationship_collection and collection_name != self.entity_collection:
            raise Exception("Unknown collection name")
        vector = self._embedding(query)
        resp = self.vectorDB.search(
            collection_name=collection_name,
            query_vector=vector,
            limit=10)
        return resp







m = LongTermMemory()
m._search_vectordb('text_collection', 'who are you')
pass
#m.insert("while Alex clenched his jaw, the buzz of frustration dull against the backdrop of Taylor's authoritarian certainty. It was this competitive undercurrent that kept him alert, the sense that his and Jordan's shared commitment to discovery was an unspoken rebellion against Cruz's narrowing vision of control and order.Then Taylor did something unexpected. They paused beside Jordan and, for a moment, observed the device with something akin to reverence. \"If this tech can be understood...\" Taylor said, their voice quieter, It could change the game for us. For all of us. The underlying dismissal earlier seemed to falter, replaced by a glimpse of reluctant respect for the gravity of what lay in their hands. Jordan looked up, and for a fleeting heartbeat, their eyes locked with Taylor's, a wordless clash of wills softening into an uneasy truce.It was a small transformation, barely perceptible, but one that Alex noted with an inward nod. They had all been brought here by different paths")