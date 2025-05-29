import ollama
import openai
from py2neo import Graph, Node, Relationship
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance,PointStruct
import hashlib
import tiktoken
import json
from dotenv import load_dotenv

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
        self.text_collection = "text_collection"
        self.community_collection = "community_collection"
        self.entity_collection = "entity_collection"
        self.relationship_collection = "relationship_collection"
        self.temporary_longterm_memory = []
        self.embedding_size = 768
        self.embedding_model = 'nomic-embed-text'
        self.llm = 'gpt-4o'
        self.llm_client = openai.OpenAI()
        self.extract_prompt = open('./extract_prompt.txt', 'r', encoding='utf-8').read()
        self.tokenizer = tiktoken.encoding_for_model(self.llm)

    def search(self, query):
        pass

    def insert(self, content:str):
        #长文本分块
        max_tokens = 1024
        tokens = self.tokenizer.encode(content)
        chunks = []
        start = 0
        while start < len(tokens):
            chunk = self.tokenizer.decode(tokens[start:start + max_tokens])
            ids = hashlib.md5(chunk.encode()).hexdigest()
            chunks.append(chunk)
            start += max_tokens
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
            for e in entity_relationship:
                if 'entity' in e:
                    attribute = {k:v for k, v in e.items() if k!='entity'}
                    attribute['vector'] = ollama.embeddings(
                        model = self.embedding_model,
                        prompt=e['description'],
                    ).embedding
                    self.graphDB.create(Node(e['entity'], **attribute))
                elif 'relationship' in e:
                    source_name = e['source']['name']
                    source_label = e['source']['type']
                    target_name = e['target']['name']
                    target_label = e['target']['type']
                    relationship = e['relationship']
                    source = self.graphDB.nodes.match(source_label, name=source_name).first()
                    target = self.graphDB.nodes.match(target_label, name=target_name).first()
                    attribute = {k:v for k, v in e.items() if k!='source' and k!='target' and k!='relationship'}
                    attribute['vector'] = ollama.embeddings(
                        model=self.embedding_model,
                        prompt=e['description'],
                    ).embedding
                    attribute['text_chunk'] = ids
                    rel = Relationship(source, relationship, target, **attribute)
                    self.graphDB.create(rel)


    def update(self):
        pass

m = LongTermMemory()
m.insert("Stock markets faced a sharp downturn today as tech giants saw significant declines, with the Global Tech Index dropping by 3.4% in midday trading. Analysts attribute the selloff to investor concerns over rising interest rates and regulatory uncertainty.Among the hardest hit, Nexon Technologies saw its stock plummet by 7.8% after reporting lower-than-expected quarterly earnings. In contrast, Omega Energy posted a modest 2.1% gain, driven by rising oil prices.Meanwhile, commodity markets reflected a mixed sentiment. Gold futures rose by 1.5%, reaching $2,080 per ounce, as investors sought safe-haven assets. Crude oil prices continued their rally, climbing to $87.60 per barrel, supported by supply constraints and strong demand.Financial experts are closely watching the Federal Reserve's next move, as speculation grows over potential rate hikes. The upcoming policy announcement is expected to influence investor confidence and overall market stability.")