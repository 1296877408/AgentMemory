extract_prompt = """
---Goal---
Given a text document that is potentially relevant to this activity and a list of entity types, identify all entities of those types from the text and all relationships among the identified entities.
use english as output language

---steps---
1.Identify all entities. For each identified entity, extract the following information:
- entity_name: Name of the entity
- entity_type: type of the entity
- entity_description: Comprehensive description of the entity's attributes and activities
Format each entity as {"entity":<entity_type>, "name":<entity_name>, "description":entity_description}

2.From the entities identified in step 1, identify all pairs of (source_entity, target_entity) that are related to each other
For each pair of related entities, extract the following information:
- relationship_name: name of the relationship which Highly generalized the relationship
- source_entity_name: name of the source entity, as identified in step 1
- source_entity_type: type of the source entity, as identified in step 1
- target_entity_name: name of the target entity, as identified in step 1
- target_entity_type: type of the target entity, as identified in step 1
- relationship_description: explanation as to why you think the source entity and the target entity are related to each other
- relationship_keywords: one or more keywords that summarize the overarching nature of the relationship, focusing on concepts or themes rather than specific details
Format each relationship as {"relationship":<relationship_name>, "source":{"name":<source_entity_name>, "type":<source_entity_type>}, "target":{"name":<target_entity_name>, "type":<target_entity_type>}, "description":<relationship_description>, "keywords":<relationship_keywords>}

3.Return output as a json list of all the entities and relationships identified in steps 1 and 2.

---Examples---
Text:
```
while Alex clenched his jaw, the buzz of frustration dull against the backdrop of Taylor's authoritarian certainty. It was this competitive undercurrent that kept him alert, the sense that his and Jordan's shared commitment to discovery was an unspoken rebellion against Cruz's narrowing vision of control and order.

Then Taylor did something unexpected. They paused beside Jordan and, for a moment, observed the device with something akin to reverence. "If this tech can be understood..." Taylor said, their voice quieter, "It could change the game for us. For all of us."

The underlying dismissal earlier seemed to falter, replaced by a glimpse of reluctant respect for the gravity of what lay in their hands. Jordan looked up, and for a fleeting heartbeat, their eyes locked with Taylor's, a wordless clash of wills softening into an uneasy truce.

It was a small transformation, barely perceptible, but one that Alex noted with an inward nod. They had all been brought here by different paths
```

Output:
'''json
[{"entity":"person","name":"Alex","description":"Alex is a character who experiences frustration and is observant of the dynamics among other characters."}
{"entity":"person","name":"Taylor","description":"Taylor is portrayed with authoritarian certainty and shows a moment of reverence towards a device, indicating a change in perspective."}
{"entity":"person","name":"Jordan","description":"Jordan shares a commitment to discovery and has a significant interaction with Taylor regarding a device."}
{"entity":"person","name":"Cruz","description":"Cruz is associated with a vision of control and order, influencing the dynamics among other characters."}
{"entity":"technology","name":"The Device","description":"The Device is central to the story, with potential game-changing implications, and is revered by Taylor."}
{"relationship":"affected by","source":{"name":"Alex","type":"person"},"target":{"name":"Taylor","type":"person"},"description":"Alex is affected by Taylor's authoritarian certainty and observes changes in Taylor's attitude towards the device.","keywords":"power dynamics, perspective shift"}
{"relationship":"share commitment","source":{"name":"Alex","type":"person"},"target":{"name":Jordan","type":"person"},"description":"Alex and Jordan share a commitment to discovery, which contrasts with Cruz's vision.","keywords":"shared goals, rebellion"}
{"relationship":"interact","source":{"name":"Taylor","type":"person"},"taget":{"name":"Jordan","type":"person"},"description":"Taylor and Jordan interact directly regarding the device, leading to a moment of mutual respect and an uneasy truce.","keywords":"conflict resolution, mutual respect"}
{"relationship":"rebellion against","source":{"name":"Jordan","type":"person"},"target":{"name":"Cruz","type":"person"},"description":"Jordan's commitment to discovery is in rebellion against Cruz's vision of control and order.","keywords":"ideological conflict, rebellion"}
{"relationship":"shows reverence","source":{"name":"Taylor","type":"person"},"target":{"name":"The Device","type":"item"},"description":"Taylor shows reverence towards the device, indicating its importance and potential impact.","keywords":"reverence, technological significance"}]
'''

---notice---
entity and relationship should include in one json,don't separate them
"""

conflict_detect_prompt = """
---Goal---
Given the extract_er which represents the new entity and relationship extract from new memory, and the exist_er which represents the old entity and relationship extract from old memory.
Compare the difference between the new entity and old entity and relationship extract from new memory, identify is there any conflict.

---format explain---
-  extract_er: the entities and relationship extract from new memory.
-  format:
to entity:
{
    entity_name: Name of the entity
    entity_type: type of the entity
    entity_description: Comprehensive description of the entity's attributes and activities
}
e.g.:{"entity":<entity_type>, "name":<entity_name>, "description":entity_description}
to relationship:
{
    relationship_name: name of the relationship which Highly generalized the relationship
    source_entity_name: name of the source entity
    source_entity_type: type of the source entity
    target_entity_name: name of the target entity
    target_entity_type: type of the target entity
    relationship_description: explanation as to why you think the source entity and the target entity are related to each other
    relationship_keywords: one or more keywords that summarize the overarching nature of the relationship, focusing on concepts or themes rather than specific details
}
e.g.:{"relationship":<relationship_name>, "source":{"name":<source_entity_name>, "type":<source_entity_type>}, "target":{"name":<target_entity_name>, "type":<target_entity_type>}, "description":<relationship_description>, "keywords":<relationship_keywords>}
-  exist_er: the entities and relationship extract from old memory.
-  format:
to entity:
{
    entity_name: the name of the entity
    entity_type: the type of the entity
    entity_ids: the unique identification of the entity
    entity_description: the description of the entity
}
e.g.:{"name":<entity_name>, "type":<entity_type>, "description":<entity_description>, "ids":<entity_id>}
to relationship:
{
    relationship_name: name of the relationship which Highly generalized the relationship
    relationship_ids: the unique identification of the relationship
    source_entity_name: name of the source entity
    source_entity_ids: id of the source entity
    target_entity_name: name of the target entity
    target_entity_ids: id of the target entity
    relationship_description: the description of the relationship
}
e.g.:{"relationship":<relationship_name>, "source":<source_entity_name>, "source_ids":<source_entity_ids>, "target":<target_entity_name>, "ids":<target_entity_ids>, "description":<relationship_description>, "keywords":<relationship_description>}}
---steps---
1.Identify all conflict based on the given information in entity description:
-  conflict:the conflict identified form given information.
-  origin_description: the original description of the entity.
-  new_description: the new description of the entity.
e.g.:{"conflict_explanation":<conflict>, "origin_description":<origin_description>, "new_description":<new_description>}"}
2.Identify all conflict based on the given information in relationship description:
-  conflict:the conflict identified form given information.
-  new_relationship_description: the new description of the relationship.
-  new_relationship: the new relationship identified form given information.
-  source_entity_id: id of the source entity.
-  source_entity_conflict_description: the description of the source entity related with old memory
-  target_entity_id: id of the target entity.
-  target_entity_conflict_description: the description of the target entity related with old memory
-  relationship_id: id of the relationship which Highly generalized the relationship
e.g.:{"conflict_explanation":<conflict>, "new_relationship_description":<new_relationship_description>, "new_relationship":<new_relationship>, "source_entity_conflict_description":<source_entity_conflict_description>, "source_id":<source_entity_id>, "target_entity_conflict_description":<target_entity_conflict_description>,"target_id":<target_entity_id>, "relationship_id":<relationship_id>}
3.Return output as a json list of all the entity conflict and relationship conflict in steps 1 and 2.

---Examples---
Input:
'''
extract_er:{
    {"entity":"person", "name":"David", "description":"David is a person who has feelings of fondness or affection towards Anna."}
    {"entity":"person", "name":"Anna", ""description" :"Anna is a person who is the object of David's affection.""}
    {'description': 'David expresses affection towards Anna, indicating a positive emotional connection.', 'keywords': 'affection, emotional connection', 'relationship': 'likes', 'source': {'name': 'David', 'type': 'person'}, 'target': {'name': 'Anna', 'type': 'person'}}
    }
exist_er:{
    {"name":"David", "type":"person", "description":["David is a person who has feelings of hate towards Anna.", "David shares a relationship of friend with John"], "ids":1}
    {"name":"Anna", "type":"person", "description":["Anna is a person who is the object of David's hate."], "ids":10}
    {"name":"John", "type":"person","description":["John is a person who is a friend of David"], "ids":7}
    {"relationship":"dislike", "relationship_id":1,"source":"David", "source_id":1, "target":"Anna", "target_id":10, "description":"David expresses hate towards Anna, indicating David negative emotional connection."}
    {"relationship": "friend", "relationship_id":2, "source":"John", "source_id":7, "target":"David", "target_id":1, "description":"John and David shares a friendship to each other."}
    }
'''
output:
'''json
[{"conflict": "In the old memory, there exists a relationship where David dislikes Anna, but the new memory indicates that David likes Anna. This forms a clear contradiction.", 
"new_relationship_description":"David expresses affection towards Anna, indicating a positive emotional connection.", 
"source_entity_conflict_description":"David is a person who has feelings of hate towards Anna.", 
"source_id":1, 
"target_id":10, 
"target_entity_conflict_description":"Anna is a person who is the object of David's hate."
"relationship_id":1}]
'''
notice: There may be no conflicts, or there may be one or multiple conflicts.Include all conflict into a json list.
"""


retrieve_agent_prompt = """
Given the original query, evidence retrieved from memory, true_evidences, identify which evidence is useful to solve the query and to solve the query is there need more evidences

---steps---
1.Decide which evidence present is useful to solve the query
evidence_format:
{   
    entity:{
        time:"the time when the entity add to memory."
        description:"it is consists of three parts, description text/create time/origin text id"
        ids:"the unique id the identify the evidence"
        name:"the name of the entity"
    },
    relationship:{
        "label": "the type of relationship"
        time:"the time when the relationship add to memory"
        keywords:"one or more keywords that summarize the overarching nature of the relationship, focusing on concepts or themes rather than specific details"
        description:"description of the relationship",
    }
    text:"the original text of those entity and relationship"
}
true_evidences:List the entity evidence, relationship evidence and text evidence you think is helpful to answer the original query.Don't change the format and content of these evidence.Just add them into the true evidence list.
2.Question yourself whether true evidences enough to answer the original query.If not, set query to the evidences you want, otherwise, set query to null.
- query:the evidences you need to answer the original query.

---example---
input:
'''json
{"Original query":"Who is Alex and what happened between Alex and Jordan.",
"true_evidences":
["Alex is a character who experiences frustration and is observant of the dynamics among other characters./2025-1-9/1"]
"evidence":
[
{"name":"Taylor","description":["Taylor is portrayed with authoritarian certainty and shows a moment of reverence towards a device, indicating a change in perspective./2025-1-7/1"}]
{"name":"Jordan", "description":["Jordan shares a commitment to discovery and has a significant interaction with Taylor regarding a device./2025-1-8/1"}]
{"name":"Cruz","description":["Cruz is associated with a vision of control and order, influencing the dynamics among other characters./2025-1-9/1"}]
{"name":"The Device","description":["The Device is central to the story, with potential game-changing implications, and is revered by Taylor./2025-1-9/2"}]
{"label":"affected by","description":"Alex is affected by Taylor's authoritarian certainty and observes changes in Taylor's attitude towards the device.","keywords":"power dynamics, perspective shift"}
{"label":"share commitment","source":{"name":"Alex","type":"person"},"target":{"name":Jordan","type":"person"},"description":"Alex and Jordan share a commitment to discovery, which contrasts with Cruz's vision.","keywords":"shared goals, rebellion"}
{"label":"rebellion against","description":"Jordan's commitment to discovery is in rebellion against Cruz's vision of control and order.","keywords":"ideological conflict, rebellion"}
{"label":"shows reverence","description":"Taylor shows reverence towards the device, indicating its importance and potential impact.","keywords":"reverence, technological significance"}]
["while Alex clenched his jaw, the buzz of frustration dull against the backdrop of Taylor's authoritarian certainty. It was this competitive undercurrent that kept him alert, the sense that his and Jordan's shared commitment to discovery was an unspoken rebellion against Cruz's narrowing vision of control and order.",
"Then Taylor did something unexpected. They paused beside Jordan and, for a moment, observed the device with something akin to reverence. "If this tech can be understood..." Taylor said, their voice quieter, "It could change the game for us. For all of us."",
"The underlying dismissal earlier seemed to falter, replaced by a glimpse of reluctant respect for the gravity of what lay in their hands. Jordan looked up, and for a fleeting heartbeat, their eyes locked with Taylor's, a wordless clash of wills softening into an uneasy truce.",
"It was a small transformation, barely perceptible, but one that Alex noted with an inward nod. They had all been brought here by different paths"]
} 
'''
output:
'''json
{
    "true_evidences":
    [
        "Jordan shares a commitment to discovery and has a significant interaction with Taylor regarding a device."
        "while Alex clenched his jaw, the buzz of frustration dull against the backdrop of Taylor's authoritarian certainty. It was this competitive undercurrent that kept him alert, the sense that his and Jordan's shared commitment to discovery was an unspoken rebellion against Cruz's narrowing vision of control and order."
    ]
    "query":what happened between Alex and Jordan.
}
'''
notice:Description is a list which contains multiple representations of an entity or relationship.If you don't need more evidence, set the query in output to null.You should include both input true evidence and new evidence you think is useful in output true evidence,follow the output format strictly.
"""
