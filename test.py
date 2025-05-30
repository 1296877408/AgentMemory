from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# 初始化 Qdrant 本地服务
client = QdrantClient("http://localhost:6333")

# 创建 collection
client.recreate_collection(
    collection_name="example",
    vectors_config=VectorParams(size=512, distance=Distance.COSINE),
)

point = [
    PointStruct(
        id=1,
        vector=[0.1]*512,
        payload={'ids': 'feqfeqe'}
    )
]
client.upsert(
    collection_name="example",
    points=point,
)
# 插入向量
# 搜索相似向量

results = client.search(
    collection_name="example",
    query_vector=[0.1]*512,
    limit=5,
)
from qdrant_client.models import Filter, FieldCondition, MatchValue

result = client.retrieve(
    collection_name="example",
    ids=[1]
)

print(result)

pass
