CONSTRAINTS_AND_INDEXES = [
    "CREATE CONSTRAINT data_source_id IF NOT EXISTS FOR (d:DataSource) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT measure_id IF NOT EXISTS FOR (m:Measure) REQUIRE m.id IS UNIQUE",
    "CREATE CONSTRAINT metric_id IF NOT EXISTS FOR (m:Metric) REQUIRE m.id IS UNIQUE",
    "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
    "CREATE CONSTRAINT graph_version_id IF NOT EXISTS FOR (v:GraphVersion) REQUIRE v.id IS UNIQUE",
    """
    CREATE VECTOR INDEX metric_desc_embedding IF NOT EXISTS
    FOR (m:Metric) ON (m.description_embedding)
    OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}
    """,
    """
    CREATE VECTOR INDEX measure_desc_embedding IF NOT EXISTS
    FOR (m:Measure) ON (m.description_embedding)
    OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}
    """,
    """
    CREATE VECTOR INDEX datasource_desc_embedding IF NOT EXISTS
    FOR (d:DataSource) ON (d.description_embedding)
    OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}
    """,
]

LINEAGE_CYCLE_QUERY = """
MATCH p = (d:DataSource)-[:SOURCED_FROM*1..]->(d)
RETURN d.id AS cyclic_node, [n IN nodes(p) | n.id] AS cycle_path
"""

COMPOSITION_CYCLE_QUERY = """
MATCH p = (m:Metric)-[:USES_COMPONENT*1..]->(m)
RETURN m.id AS cyclic_node, [n IN nodes(p) | n.id] AS cycle_path
"""

CANONICAL_DUPLICATE_QUERY = """
MATCH (a:DataSource)-[j:JOINS_TO {canonical: true}]-(b:DataSource)
WITH a, b, count(j) AS canonical_count
WHERE canonical_count > 1
RETURN a.id AS source_id, b.id AS target_id, canonical_count
"""
