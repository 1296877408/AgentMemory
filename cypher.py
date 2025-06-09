search_exist_r = """
unwind $ids as id1
unwind $ids as id2
match (n{ids:id1})-[r]->(m{ids:id2})
return r
"""

search_exist_e = """
unwind $entity as n
with n["entity"] as t, n
unwind t as type
match (m:type {name: n["name"]}) 
return m
"""

search_by_ids_entity = """
unwind $ids as ids
match (n {ids:ids})
return n
"""

search_by_ids_relationship = """
unwind $ids as ids
match (a)-[r{ids:ids}]->(b)
return r
"""

insert_entity = """
unwind $label as label
unwind $props as props
create (n:label) set n = props
return n
"""

insert_update="""
with $ids as ids, $description as description
match (n{ids:ids})
set n.description = n.description + description
return n
"""

insert_relationship = """
unwind $source_id as sid
unwind $target_id as tid
unwind $label as label
unwind $props as props
match (n{ids:sid})
match (m{ids:tid})
create (n)-[r:label]->(m)
set r = props
return r
"""





