// service.cypher — SERVICE ingestion from service JSON files (bulk: one doc per file).
// Parameters (supplied by load.py on every statement):
//   $docs — list of parsed service documents, one element per input file
// Requires APOC: apoc.text.join, apoc.meta.cypher.isType, apoc.create.addLabels.
//
// Model (per the holistic entities/relations diagram):
//   (:COMPONENT)-[:CONSISTS_OF]->(:SERVICE)
//   (:SERVICE)-[:CONSUMES]->(:DATA_MODEL)   // inputDataModel
//   (:SERVICE)-[:PRODUCES]->(:DATA_MODEL)   // outputDataModels[]  (enriched_complete on rel)
//   (:SERVICE)-[:REFERS]->(:DATA_MODEL)     // referencedModels[]
//   (:SERVICE)-[:EXECUTES]->(:FLOW)         // flow[]  (path basename = flow kgId)
// Cross-referenced DATA_MODEL / FLOW nodes are MERGEd as stubs (ON CREATE SET node_type)
// and enriched when their own cyphers run.

// --- 1. SERVICE node ---
UNWIND $docs AS doc
MERGE (s:SERVICE {node_kg_id: doc.kgId})
SET s.node_name        = coalesce(doc.name, ''),
    s.node_type        = 'SERVICE',
    s.node_complete     = true,
    s.component_name   = coalesce(doc.metadata.repoName, ''),
    s.generated_from   = coalesce(doc.metadata.generatedFrom, ''),
    s.generated_at     = coalesce(doc.metadata.generatedAt, ''),
    s.version          = coalesce(doc.metadata.version, ''),
    s.domain           = coalesce(doc.domain, ''),
    s.operation_type   = coalesce(doc.operationType, ''),
    s.invocation_types = coalesce(doc.invocationType, []),
    s.request_type     = coalesce(doc.requestType, ''),
    s.response_type    = coalesce(doc.responseType, ''),
    s.engine           = coalesce(doc.engine, ''),
    s.enable_audit     = doc.enableAudit,
    s.node_description  = CASE
        WHEN doc.description IS NULL THEN ''
        WHEN apoc.meta.cypher.isType(doc.description, 'LIST OF STRING') THEN apoc.text.join(doc.description, '\n')
        ELSE toString(doc.description) END
WITH s,
  [l IN [s.operation_type] WHERE l IS NOT NULL AND l <> '' | toString(l)] +
  [l IN [s.engine]         WHERE l IS NOT NULL AND l <> '' | toString(l)] AS extra_labels
WHERE size(extra_labels) > 0
CALL apoc.create.addLabels(s, extra_labels) YIELD node AS _
RETURN count(*) AS total;

// --- 2. COMPONENT -[:CONSISTS_OF]-> SERVICE ---
UNWIND $docs AS doc
WITH doc, coalesce(doc.metadata.repoName, '') AS repoName
WHERE repoName <> ''
MERGE (c:COMPONENT {node_kg_id: repoName})
ON CREATE SET c.node_type = 'COMPONENT', c.node_complete = false
MERGE (s:SERVICE {node_kg_id: doc.kgId})
MERGE (c)-[:CONSISTS_OF]->(s);

// --- 3. SERVICE -[:CONSUMES]-> DATA_MODEL (inputDataModel) ---
UNWIND $docs AS doc
WITH doc, doc.inputDataModel.modelKgId AS inModel
WHERE inModel IS NOT NULL AND inModel <> ''
MERGE (s:SERVICE {node_kg_id: doc.kgId})
MERGE (dm:DATA_MODEL {node_kg_id: inModel})
ON CREATE SET dm.node_type = 'DATA_MODEL', dm.node_complete = false
MERGE (s)-[:CONSUMES]->(dm);

// --- 4. SERVICE -[:PRODUCES]-> DATA_MODEL (outputDataModels[]) ---
UNWIND $docs AS doc
UNWIND coalesce(doc.outputDataModels, []) AS out
WITH doc, out WHERE out.modelKgId IS NOT NULL AND out.modelKgId <> ''
MERGE (s:SERVICE {node_kg_id: doc.kgId})
MERGE (dm:DATA_MODEL {node_kg_id: out.modelKgId})
ON CREATE SET dm.node_type = 'DATA_MODEL', dm.node_complete = false
MERGE (s)-[r:PRODUCES]->(dm)
SET r.enriched_complete = out.enrichedProperties.complete,
    r.enriched_partial_kg_ids = [p IN coalesce(out.enrichedProperties.partial, []) | p.propertyKgId];

// --- 5. SERVICE -[:REFERS]-> DATA_MODEL (referencedModels[]) ---
UNWIND $docs AS doc
UNWIND coalesce(doc.referencedModels, []) AS rm
WITH doc, rm WHERE rm.modelKgId IS NOT NULL AND rm.modelKgId <> ''
MERGE (s:SERVICE {node_kg_id: doc.kgId})
MERGE (dm:DATA_MODEL {node_kg_id: rm.modelKgId})
ON CREATE SET dm.node_type = 'DATA_MODEL', dm.node_complete = false
MERGE (s)-[r:REFERS]->(dm)
SET r.referenced_property_kg_ids = [p IN coalesce(rm.referencedProperties, []) | p.propertyKgId];

// --- 6. SERVICE -[:EXECUTES]-> FLOW (flow[] path basenames) ---
UNWIND $docs AS doc
UNWIND coalesce(doc.flows, []) AS flowRef
WITH doc, flowRef.flowKgId AS flowKgId
WHERE flowKgId IS NOT NULL AND flowKgId <> ''
MERGE (s:SERVICE {node_kg_id: doc.kgId})
MERGE (f:FLOW {node_kg_id: flowKgId})
ON CREATE SET f.node_type = 'FLOW', f.node_complete = false
MERGE (s)-[:EXECUTES]->(f);
