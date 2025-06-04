from py2neo import Graph

# 连接到 Neo4j 数据库
graph = Graph("bolt://localhost:7687", auth=("neo4j", "aA007812"))

# 定义参数
names = ["a", "b", "c"]

# 执行查询
query = """
UNWIND $names AS name1
UNWIND $names AS name2
match (n1 {name:name1})
match (n2 {name:name2})
where n1.name <> n2.name
match (n1)-[r1]->(n2)
RETURN n1, n2, r1
"""

# 运行查询并传入参数
result = graph.run(query, names=names)

# 输出结果
for record in result:
    print(record)
    pass
