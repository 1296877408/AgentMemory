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

load_dotenv()

class LongTermMemory:
    def __init__(self, config:dict):
