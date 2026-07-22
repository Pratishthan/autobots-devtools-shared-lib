// behaviour.cypher — BEHAVIOUR (LPU) ingestion from logical-processing-unit JSON files (bulk).
// Parameters (supplied by load.py on every statement):
//   $docs — list of parsed LPU documents, one element per input file
// Requires APOC: apoc.create.addLabels.
//
// Model (per the holistic entities/relations diagram + seed):
//   (:BEHAVIOUR)-[:CONSUMES]->(:DATA_MODEL)         // consumes.Models[] + consumes.dataReaders[]
//   (:BEHAVIOUR)-[:PRODUCES]->(:DATA_MODEL)         // produces.Models[] + produces.dataWriters[]  (enriched_complete on rel)
//   (:BEHAVIOUR)-[:USES_DATA_ACCESS]->(:DATA_ACCESS) // dataReaders[]/dataWriters[].dataAccessKgId
//   (:DATA_ACCESS)-[:QUERIES]->(:DATA_MODEL)        // pairs dataAccessKgId + modelKgId (the edge interface-data_access.cypher cannot derive)
// This cypher owns the BEHAVIOUR node properties — it enriches stubs that flow.cypher plants.
// Cross-referenced DATA_MODEL / DATA_ACCESS nodes are MERGEd as stubs (ON CREATE SET node_type)
// and enriched when their own cyphers run.
// Primitives (consumes/produces) are not modelled: their primitiveKgId is empty in the source.

// --- 1. BEHAVIOUR node ---
UNWIND $docs AS doc
MERGE (b:BEHAVIOUR {node_kg_id: doc.kgId})
SET b.node_name       = doc.name,
    b.node_type       = 'BEHAVIOUR',
    b.node_complete    = true,
    b.component_name  = coalesce(doc.metadata.repoName, ''),
    b.generated_from  = coalesce(doc.metadata.generatedFrom, ''),
    b.generated_at    = coalesce(doc.metadata.generatedAt, ''),
    b.version         = coalesce(doc.metadata.version, ''),
    b.behaviour_type  = doc.type,
    b.sub_type        = doc.subType,
    b.business_logic  = coalesce(doc.businessLogic, []),
    b.error_constants = coalesce(doc.errorConstants, [])
WITH b
CALL apoc.create.addLabels(b,
  [l IN [b.behaviour_type] WHERE l IS NOT NULL AND l <> '' | toString(l)] +
  [l IN [b.sub_type]       WHERE l IS NOT NULL AND l <> '' | toString(l)]
) YIELD node AS _
RETURN count(*) AS total;

// --- 2. CONSUMES -> DATA_MODEL (consumes.Models[]) ---
UNWIND $docs AS doc
UNWIND coalesce(doc.consumes.Models, []) AS m
WITH doc, m WHERE m.modelKgId IS NOT NULL AND m.modelKgId <> ''
MERGE (b:BEHAVIOUR {node_kg_id: doc.kgId})
MERGE (dm:DATA_MODEL {node_kg_id: m.modelKgId})
ON CREATE SET dm.node_type = 'DATA_MODEL', dm.node_complete = false
MERGE (b)-[r:CONSUMES]->(dm)
SET r.referenced_property_kg_ids = [p IN coalesce(m.referencedProperties, []) | p.propertyKgId];

// --- 3. CONSUMES + USES_DATA_ACCESS + QUERIES (consumes.dataReaders[]) ---
UNWIND $docs AS doc
UNWIND coalesce(doc.consumes.dataReaders, []) AS dr
WITH doc, dr WHERE dr.modelKgId IS NOT NULL AND dr.modelKgId <> ''
MERGE (b:BEHAVIOUR {node_kg_id: doc.kgId})
MERGE (dm:DATA_MODEL {node_kg_id: dr.modelKgId})
ON CREATE SET dm.node_type = 'DATA_MODEL', dm.node_complete = false
MERGE (b)-[r:CONSUMES]->(dm)
SET r.referenced_property_kg_ids = [p IN coalesce(dr.referencedProperties, []) | p.propertyKgId]
WITH b, dm, dr WHERE dr.dataAccessKgId IS NOT NULL AND dr.dataAccessKgId <> ''
MERGE (da:DATA_ACCESS {node_kg_id: dr.dataAccessKgId})
ON CREATE SET da.node_type = 'DATA_ACCESS', da.node_complete = false
MERGE (b)-[:USES_DATA_ACCESS]->(da)
MERGE (da)-[:QUERIES]->(dm);

// --- 4. PRODUCES -> DATA_MODEL (produces.Models[], enriched_complete on rel) ---
UNWIND $docs AS doc
UNWIND coalesce(doc.produces.Models, []) AS m
WITH doc, m WHERE m.modelKgId IS NOT NULL AND m.modelKgId <> ''
MERGE (b:BEHAVIOUR {node_kg_id: doc.kgId})
MERGE (dm:DATA_MODEL {node_kg_id: m.modelKgId})
ON CREATE SET dm.node_type = 'DATA_MODEL', dm.node_complete = false
MERGE (b)-[r:PRODUCES]->(dm)
SET r.enriched_complete = m.enrichedProperties.complete;

// --- 5. PRODUCES + USES_DATA_ACCESS + QUERIES (produces.dataWriters[]) ---
UNWIND $docs AS doc
UNWIND coalesce(doc.produces.dataWriters, []) AS dw
WITH doc, dw WHERE dw.modelKgId IS NOT NULL AND dw.modelKgId <> ''
MERGE (b:BEHAVIOUR {node_kg_id: doc.kgId})
MERGE (dm:DATA_MODEL {node_kg_id: dw.modelKgId})
ON CREATE SET dm.node_type = 'DATA_MODEL', dm.node_complete = false
MERGE (b)-[r:PRODUCES]->(dm)
SET r.enriched_complete = dw.enrichedProperties.complete
WITH b, dm, dw WHERE dw.dataAccessKgId IS NOT NULL AND dw.dataAccessKgId <> ''
MERGE (da:DATA_ACCESS {node_kg_id: dw.dataAccessKgId})
ON CREATE SET da.node_type = 'DATA_ACCESS', da.node_complete = false
MERGE (b)-[:USES_DATA_ACCESS]->(da)
MERGE (da)-[:QUERIES]->(dm);

// --- 6. COMPONENT stub auto-creation ---
UNWIND $docs AS doc
WITH coalesce(doc.metadata.repoName, '') AS repoName
WHERE repoName <> ''
MERGE (c:COMPONENT {node_kg_id: repoName})
ON CREATE SET c.node_type = 'COMPONENT', c.node_complete = false
