from email.encoders import encode_noop

import ollama
import openai
from numpy.ma.core import true_divide
from py2neo import Graph, Node, Relationship, Node
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance,PointStruct
import hashlib
import tiktoken
import json
from dotenv import load_dotenv
import time
import configparser

from scripts.regsetup import description

import cypher
import prompt

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
            self.mem_num = json.load(f)
        self.max_chunk_token = 512
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
        tools = [
            {
                "type": "function",
                "function":{
                    "name": "_search",
                    "description": "get memory related to query",
                    "parameters":{
                        "type":"object",
                        "properties":{
                            "query": {"type": "string", "description": "based on the current given evidence to answer the origin query what you need else"}
                            },
                        "required": ["query"]
                    }
                }
            }
        ]
        evidences = self._search(query)
        true_evidences = set()
        for term in range(5):
            inputs = str({"origin_query": query, "true_evidence": list(true_evidences), "evidences": evidences})
            print(inputs)
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": prompt.retrieve_agent_prompt},
                    {"role": "user", "content": inputs}
                ],
                tools=tools,
                tool_choice="auto"
            )
            try:
                output = json.loads(response.choices[0].message.content[7:-4])
                print(output)
            except:
                output = json.loads(response.choices[0].message.content)
                print(output)
            true_evidences = true_evidences | set(output['true_evidences'])
            query = output['query']
            if query:
                evidences = self._search(query)
                continue
            else:
                break

        return true_evidences

    def _search(self, query):
        evidences = []
        text_id = set()
        community = self._search_vectordb(collection_name=self.community_collection, query=query)
        if len(community):
            pass
        else:
            e = self._search_vectordb(collection_name=self.entity_collection, query=query)
            r = self._search_vectordb(collection_name=self.relationship_collection, query=query)
            entity = [self._search_graphdb_by_id("entity", node.payload['id'])[0]['n'] for node in e]
            relationship = [self._search_graphdb_by_id("relationship", node.id)[0]['r'] for node in r]

        for ee in entity:
            evidences.append({"name": ee["name"], "description": ee["description"]})
            tid = [d.split("/")[-1] for d in ee['description']]
            text_id.union(set(tid))
        for rr in relationship:
            evidences.append({"label": type(rr).__name__, "description": rr['description'], "keywords": rr['keywords']})
            tid = rr["text"]
            text_id.add(tid)
        for ids in text_id:
            evidences.append(
                (self._search_vectordb_by_id(collection_name=self.text_collection, ids=[ids]))[0].payload["text"])
        print(evidences)
        return evidences


    def insert(self, text:str):
        """
        agent知识初始化，不进行冲突检查
        :param text:
        :return:
        """
        all_token = self.tokenizer.encode(text)
        for i in range(0, len(all_token), self.max_chunk_token):
            chunk = self.tokenizer.decode(all_token[i:i + self.max_chunk_token])
            if self._is_exist_text(collection_name=self.text_collection, query=chunk):
                continue
            else:
                self._insert_vectordb(collection_name=self.text_collection, text=chunk, ids=self.mem_num['chunk_num'])
                extract_er = self._extract_er(chunk)
                exist_e, exist_r = self._get_exist_er(extract_er)
                extract_er = self._insert_update_db(exist_e, extract_er)
                for er in extract_er:
                    if "entity" in er:
                        self._insert_vectordb(collection_name=self.entity_collection, text=er['description'])
                        self._insert_graphdb(er)

                    elif "relationship" in er:
                        self._insert_vectordb(collection_name=self.relationship_collection, text=er['description'])
                        self._insert_graphdb(er)
            self.mem_num['chunk_num'] +=1
            self.write_num()

    def merge(self):
        """
        将临时长期记忆merge到长期记忆中，创建community
        :return:
        """
    def update(self):
        """

        :return:
        """

        """
        conflict = self._detect_conflict(exist_e, exist_r, extract_er)
        if conflict:
            self._address_conflict(conflict)
        """
    def _make_evidence(self, er):
        if isinstance(er, Node):
            return {"time":er['latest_update'], "name":er['name'], 'description':er['description']}
        elif isinstance(er, Relationship):
            return {"label":type(er).__name__,"time":er['latest_update'], "name":er['name'],"keywords":er['keywords'],'description':er['description']}
        else:
            return None

    def write_num(self):
        with open('./mem_num.json', "w", encoding="utf-8") as f:
            json.dump(self.mem_num, f, ensure_ascii=False, indent=4)

    def _detect_conflict(self, exist_e:list, exist_r, extract_er):
        exist_er = exist_e + exist_r
        if len(exist_er) == 0:
            exist_er = None
        query = {"extract_er":extract_er, "exist_er":exist_er}
        query = "'''json\n" + str(query) + "'''"
        response = self.llm_client.chat.completions.create(
            model=self.llm,
            messages=[
                {"role": "system", "content": prompt.conflict_detect_prompt},
                {"role": "user", "content": query}
            ]
        )
        return json.loads(response.choices[0].message.content[7:-4])

    def _address_conflict(self, conflict):
        pass

    def _insert_update_db(self, exist_e, extract_er:list):
        updated = []
        for er in extract_er:
            if "entity" in er:
                name = er['name']
                typ = er['entity']
                for ee in exist_e:
                    if ee['name'] == name and ee['type'] == typ:
                        desc = [er["description"]+'/'+time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))+'/'+str(self.mem_num['chunk_num'])]
                        self.graphDB.run(cypher=cypher.insert_update, ids=ee['ids'], description=ee['description'] + desc)
                        self._insert_vectordb(collection_name=self.entity_collection, ids=self.mem_num['entity_num'], text=er['description'])
                        updated.append(er)
        return [eee for eee in extract_er if eee not in updated]

    def _insert_graphdb(self, er:dict):
        if "entity" in er:
            label = er.pop("entity")
            er['ids'] = self.mem_num['entity_num']
            er['create_time'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
            er["description"] = [er["description"]+'/'+er["create_time"]+'/'+str(self.mem_num['chunk_num'])]
            er['latest_update'] = er['create_time']
            er['used'] = 0
            self.mem_num['entity_num'] += 1
            self.mem_num['entity_description_num'] += 1
            node = Node(label, **er)
            self.graphDB.create(node)
        elif "relationship" in er:
            label = er.pop('relationship')
            source = er.pop('source')
            target = er.pop('target')
            source_id = self.graphDB.nodes.match(source["type"], name=source["name"]).first()
            target_id = self.graphDB.nodes.match(target["type"], name=target["name"]).first()
            er['text'] = self.mem_num['chunk_num']
            er['used'] = 0
            er['ids'] = self.mem_num['relationship_num']
            er['create_time'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
            er['latest_update'] = er['create_time']
            self.mem_num['relationship_num'] += 1
            rel = Relationship(source_id, label, target_id, **er)
            self.graphDB.merge(rel)


    def _search_graphdb(self, query:str):
        """
        使用用户询问搜索数据库中相应的entity，relationship和text
        返回类型为list[Record]
        :param query: 用户询问
        :return: 搜索到的entity，relationship和text
        """
        community_resp = self._search_vectordb(collection_name=self.community_collection, query=query)
        community_resp = [resp for resp in community_resp if resp.score>=0.7]
        entity = []
        relationship = []
        text = []
        if len(community_resp):
            for c in community_resp:
                text.append(c.text)
                text = c.text
                entity_id = c.entity
                relationship_id = c.relationship
                entity.append(self._search_graphdb_by_id(search_type='entity', ids=entity_id))
                relationship.append(self._search_graphdb_by_id(search_type='relationship',ids=relationship_id))
            return {"entity": entity, "relationship": relationship, "text": text}

        else:
            entity_id = [entity.id for entity in self._search_vectordb(collection_name=self.entity_collection, query=query)]
            relationship_id = [relationship.id for relationship in self._search_vectordb(collection_name=self.relationship_collection, query=query)]
            entity.append(self._search_graphdb_by_id(search_type='entity', ids=entity_id))
            relationship.append(self._search_graphdb_by_id(search_type='relationship',ids=relationship_id))
            return {"entity": entity, "relationship": relationship}

    def _search_graphdb_by_id(self, search_type:str, ids:list):
        """
        通过id查找数据库中指定的entity和relationship
        :param search_type: 查找类型，entity或者relationship
        :param ids: 指定节点的id
        :return: 返回查询结果列表
        """
        if search_type == 'entity':
            resp = self.graphDB.run(cypher=cypher.search_by_ids_entity, ids=ids)
            resp = list(resp)
            return resp
        elif search_type == 'relationship':
            resp = self.graphDB.run(cypher=cypher.search_by_ids_relationship, ids=ids)
            resp = list(resp)
            return resp
        else:
            raise Exception(f'Unknown search type: {search_type}')

    def _insert_vectordb(self, collection_name:str, text:str, ids:int=0):
        """
        将数据插入到向量数据库中
        :param collection_name:
        :param text:
        :return:
        """
        if collection_name == self.text_collection:
            point = PointStruct(
                id=ids,
                vector=self._embedding(text),
                payload={"text": text}
            )
            self.vectorDB.upsert(
                collection_name=collection_name,
                points=[point],
            )
            return
        elif collection_name == self.entity_collection:
            if ids == 0:
                point = self._create_point(description_ids=self.mem_num['entity_description_num'], text=text, item_ids=self.mem_num['entity_num'])
                self.vectorDB.upsert(
                collection_name=collection_name,
                points=[point],
                )
                self.mem_num['entity_description_num'] += 1
            else:
                point = self._create_point(description_ids=self.mem_num['entity_description_num'], text=text, item_ids=ids)
                self.vectorDB.upsert(
                collection_name=collection_name,
                points=[point],
                )
                self.mem_num['entity_description_num'] += 1
                return
        elif collection_name == self.relationship_collection:
            point = self._create_point(description_ids=self.mem_num['relationship_num'], text=text, item_ids=self.mem_num['relationship_num'])
            self.vectorDB.upsert(
                collection_name=collection_name,
                points=[point],
            )
            return
        elif collection_name == self.community_collection:
            point = self._create_point(description_ids=self.mem_num['community_num'], text=text, item_ids=self.mem_num['community_num'])
            self.vectorDB.upsert(
                collection_name=collection_name,
                points=[point],
            )
            self.mem_num['community_num'] += 1
            return

    def _extract_er(self, query:str):
        """
        使用llm从文本中提取相应的entity和relationship
        :param query:
        :return:
        """
        response = self.llm_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt.extract_prompt},
                {"role": "user", "content": query}
            ]
        )
        entity_relationship = response.choices[0].message.content
        return json.loads(entity_relationship[7:-4])

    def _get_exist_er(self, extract_er:dict):
        """

        :param extract_er:
        :return:
        """
        entity = [{'name': e["name"], 'type': e["entity"]} for e in extract_er if 'entity' in e]
        exist_e = []
        for e in entity:
            exist_e.append(self.graphDB.nodes.match(e["type"], name=e["name"]).first())
        exist_e = list(filter(lambda x:x is not None, exist_e))
        if len(exist_e):
            ids = [e['ids'] for e in exist_e]
        else:
            ids = []
        exist_r = list(self.graphDB.run(cypher=cypher.search_exist_r, ids=ids))

        exist_e = [{'name': e['name'], 'type': list(e.labels)[0], 'ids': e['ids'], 'description': e['description']} for e in exist_e]
        exist_r = [{"relationship": type(r['r']).__name__, "relationship_ids": r['r']['ids'],"source": r['r'].start_node['name'], "source_ids": r['r'].start_node['ids'],"target": r['r'].end_node['name'], "target_ids": r['r'].end_node['ids'],"description": r['r']['description']} for r in exist_r]
        return exist_e, exist_r

    def _embedding(self, query:str):
        """
        将query转化为向量表示
        :param query:
        :return:
        """
        return ollama.embeddings(
            model=self.embedding_model,
            prompt=query,
        ).embedding

    def _create_point(self, description_ids:int, text:str, item_ids:int):
        """
        创建插入到向量数据库中的节点
        :param text:
        :return:
        """
        vector = self._embedding(text)
        return PointStruct(
            id=description_ids,
            vector=vector,
            payload={"id":item_ids}
        )

    def _is_exist_text(self, collection_name:str, query:str):
        """
        判断文本块是否已经存在
        :param collection_name:
        :param query:
        :return:
        """
        if collection_name != self.text_collection and collection_name != self.entity_collection and collection_name != self.relationship_collection and collection_name != self.entity_collection:
            raise Exception("Unknown collection name")
        vector = self._embedding(query)
        resp = self.vectorDB.search(collection_name=collection_name,query_vector=vector,score_threshold=0.9)
        if len(resp) == 0:
            return False
        else:
            return True

    def _search_vectordb_by_id(self, collection_name:str, ids:list[int]):
        """
        通过id查找向量数据库中的节点
        :param collection_name:
        :param ids:
        :return:
        """
        if collection_name != self.text_collection and collection_name != self.entity_collection and collection_name != self.relationship_collection and collection_name != self.entity_collection:
            raise Exception("Unknown collection name")
        points = self.vectorDB.retrieve(collection_name=collection_name,ids=ids)
        return points


    def _search_vectordb(self, collection_name, query:str)->list:
        """
        通过query查找向量数据库中的节点
        :param collection_name:
        :param query:
        :return:
        """
        if collection_name != self.community_collection and collection_name != self.entity_collection and collection_name != self.relationship_collection and collection_name != self.entity_collection:
            raise Exception("Unknown collection name")
        vector = self._embedding(query)
        if collection_name == self.community_collection:
            resp = self.vectorDB.search(
                collection_name=collection_name,
                query_vector=vector,
                limit=10,
                score_threshold=0.7
            )
        else:
            resp = self.vectorDB.search(
                collection_name=collection_name,
                query_vector=vector,
                limit=10,
                score_threshold=0.5
            )
        return resp
"""
m = LongTermMemory()
m._insert_vectordb(collection_name="text_collection", ids=9, text="a is a person who's friend is b")
er = m._extract_er("a is a person who like b")
er = json.loads(er)
exist_e, exist_r = m._get_exist_er(query="a is a person who like b")
k = 1
for i in er:
    if 'entity' in i:
        m._insert_vectordb(collection_name="entity_collection", ids=k, text=i['description'])
    if 'relationship' in i:
        m._insert_vectordb(collection_name="relationship_collection", ids=k, text=i['description'])
    k += 1

m._search_vectordb('text_collection', "a is a person who's friend is b")
entity_id = [entity.id for entity in m._search_vectordb('entity_collection', "a is a person who's friend is b")]
m._search_graphdb_by_id('entity',ids=entity_id)
pass
#m.insert("while Alex clenched his jaw, the buzz of frustration dull against the backdrop of Taylor's authoritarian certainty. It was this competitive undercurrent that kept him alert, the sense that his and Jordan's shared commitment to discovery was an unspoken rebellion against Cruz's narrowing vision of control and order.Then Taylor did something unexpected. They paused beside Jordan and, for a moment, observed the device with something akin to reverence. \"If this tech can be understood...\" Taylor said, their voice quieter, It could change the game for us. For all of us. The underlying dismissal earlier seemed to falter, replaced by a glimpse of reluctant respect for the gravity of what lay in their hands. Jordan looked up, and for a fleeting heartbeat, their eyes locked with Taylor's, a wordless clash of wills softening into an uneasy truce.It was a small transformation, barely perceptible, but one that Alex noted with an inward nod. They had all been brought here by different paths")"""
m = LongTermMemory()
m.insert("黄昏时分，咖啡馆里坐着三个人。老板周琴正在吧台后面煮着一壶手冲咖啡，她总是沉稳寡言，但眼神中藏着故事。靠窗的位置是她的老朋友沈川，一位退休教师，他每天都来，点一杯黑咖啡，看一本哲学书。沈川常说，他是来看人而不是来看书的。他和周琴认识了二十多年，彼此了解，却从未明说过关系。今天，沈川带来了自己的学生许可，一个大学刚毕业的年轻人，文静而敏感。他在考虑是否要追随沈川的脚步，成为一名教师，但也害怕重复沈川孤独的人生。聊天中，许可第一次听周琴说起自己年轻时放弃教师工作的决定，也第一次看到沈川对她流露出惋惜与尊重。他忽然意识到，选择职业不仅是选择一条路，更是选择与谁一起走。")
m.insert("在南湖小镇的旧书店里，店主李叔每天早晨都会准时打开店门。他是这个小镇最受尊敬的长者之一。年轻的林然常来这里看书，他是一名在外地工作的记者，最近请假回来照顾生病的母亲。李叔对林然很欣赏，常常给他推荐一些老报刊。林然的中学同学苏婧也回到了小镇，她是镇医院新来的医生。他们已经十年未见，如今重逢，两人常在书店外的长椅上聊很久，谈梦想，也谈各自的人生选择。而李叔的外孙女李萌是苏婧的病人，因长期失眠来医院复诊。苏婧发现李萌的焦虑似乎与父母离婚有关，于是联系了李叔商量对策。李叔第一次意识到，自己一直忽略了李萌内心的情绪。")
m.search("林然是谁？苏婧是谁？李叔是谁？林然和苏婧之间的关系如何发展？李叔是如何通过苏婧重新理解李萌的问题的？这反映了什么样的代际沟通困境？")
m.search("2025年6月都有哪些新记忆")
