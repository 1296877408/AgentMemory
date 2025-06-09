from qdrant_client import QdrantClient
from qdrant_client.models import Filter
from qdrant_client.http import models
client = QdrantClient(
    host="localhost",
    port=6333
)
client.recreate_collection(collection_name="community_collection", vectors_config=models.VectorParams(
        size=768,          # 向量维度，比如 512 维
        distance=models.Distance.COSINE))
client.delete(collection_name='text_collection', points_selector=Filter(must=[]))
client.delete(collection_name='entity_collection', points_selector=Filter(must=[]))
client.delete(collection_name='relationship_collection', points_selector=Filter(must=[]))
client.delete(collection_name='community_collection', points_selector=Filter(must=[]))