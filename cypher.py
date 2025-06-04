search_exist_r = """
unwind $entity as n1
unwind $entity as n2
with n1, n2 where n1 <> n2
match (n {name: n1["name"], type: n1["type"]})-[r]->(m {name: n2["name"], type: n2["type"]})
return r
"""

search_exist_e = """
unwind $entity as n
match (m {name: n1["name"], type: n1["type"]}) 
return m
"""

search_by_ids = """

"""




