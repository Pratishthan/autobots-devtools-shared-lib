// interface-sync.cypher — SYNC interface ingestion from sync-interface JSON files (bulk, OpenAPI shape).
// Parameters (supplied by load.py on every statement):
//   $docs — list of parsed interface documents, one element per input file
// Requires APOC: apoc.create.addLabels.
//
// Model (per the holistic entities/relations diagram + seed):
//   (:SYNC)-[:INVOKES_SERVICE]->(:SERVICE)
// The SERVICE is referenced by x-fbp-params.serviceKgId VERBATIM (no transformation).
// Request/response model kgIds are kept as properties on the SYNC node, not as edges
// (the service owns the consumes/produces edges to those models).
//
// Each operation lives at doc.paths[<path>][<httpMethod>], with x-fbp-params carrying
// interfaceKgId / serviceKgId / inputDataModel / outputDataModel.

// --- 1. SYNC node ---
// node_kg_id = x-fbp-params.interfaceKgId; node_name = last '-' segment of it;
// component_name = the segment before '-Sync-'. http_method from the path-item key.
UNWIND $docs AS doc
UNWIND keys(coalesce(doc.paths, {})) AS pathKey
WITH doc, pathKey, doc.paths[pathKey] AS pathItem
UNWIND keys(pathItem) AS method
WITH doc, pathKey, method, pathItem[method] AS op
WHERE toLower(method) IN ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']
WITH doc, pathKey, method, op, op.`x-fbp-params` AS fbp
WHERE fbp IS NOT NULL AND fbp.interfaceKgId IS NOT NULL AND fbp.interfaceKgId <> ''
MERGE (sync:SYNC {node_kg_id: fbp.interfaceKgId})
SET sync.node_name           = last(split(fbp.interfaceKgId, '-')),
    sync.node_type           = 'SYNC',
    sync.node_complete        = true,
    sync.component_name      = coalesce(doc.metadata.repoName, ''),
    sync.generated_from      = coalesce(doc.metadata.generatedFrom, ''),
    sync.generated_at        = coalesce(doc.metadata.generatedAt, ''),
    sync.version             = coalesce(doc.metadata.version, ''),
    sync.node_description    = coalesce(op.description, ''),
    sync.path                = pathKey,
    sync.http_method         = toUpper(method),
    sync.single_response     = fbp.singleResponse,
    sync.request_model_kg_id  = fbp.inputDataModel.modelKgId,
    sync.response_model_kg_id = fbp.outputDataModel.modelKgId
WITH sync WHERE sync.http_method IS NOT NULL AND sync.http_method <> ''
CALL apoc.create.addLabels(sync, [sync.http_method]) YIELD node AS _
RETURN count(*) AS total;

// --- 2. SYNC -[:INVOKES_SERVICE]-> SERVICE (serviceKgId used verbatim) ---
UNWIND $docs AS doc
UNWIND keys(coalesce(doc.paths, {})) AS pathKey
WITH doc.paths[pathKey] AS pathItem
UNWIND keys(pathItem) AS method
WITH method, pathItem[method] AS op
WHERE toLower(method) IN ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']
WITH op.`x-fbp-params` AS fbp
WHERE fbp.interfaceKgId IS NOT NULL AND fbp.interfaceKgId <> ''
  AND fbp.serviceKgId IS NOT NULL AND fbp.serviceKgId <> ''
MERGE (sync:SYNC {node_kg_id: fbp.interfaceKgId})
MERGE (svc:SERVICE {node_kg_id: fbp.serviceKgId})
ON CREATE SET svc.node_type = 'SERVICE', svc.node_complete = false
MERGE (sync)-[:INVOKES_SERVICE]->(svc);
