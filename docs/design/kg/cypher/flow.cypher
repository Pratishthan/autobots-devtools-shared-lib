// flow.cypher — FLOW ingestion from flow JSON files (bulk: PM = PROCESS_MANAGER, CM = COMPOSE_FLOW).
// Parameters (supplied by load.py on every statement):
//   $docs — list of parsed flow documents, one element per input file
// Requires APOC: apoc.create.addLabels.
//
// Faithful model (per the holistic entities/relations diagram):
//   (:FLOW)-[:CONSISTS_OF]->(:STATE | :ACTION | :CONDITION | :BEHAVIOUR)
//   (:ACTION)-[:INVOKES_FLOW]->(:FLOW)          // Action.$ref -> referenced CM flow
//   (pn)-[:TRANSITIONS_TO {path, step}]->(pn)   // from flowPaths
// State/Action/Condition processing nodes are keyed by their own nodeId.
// Behaviour processing nodes resolve to the BEHAVIOUR(LPU) node (node_kg_id = LPU kgId,
// derived from props.behaviour.$ref) so the flow links to the same node behaviour.cypher owns.

// --- 1. FLOW node ---
// node_name: use doc.name when present; otherwise derive — COMPOSE_FLOW = feature-operation,
// PROCESS_MANAGER = the last '--'-delimited segment of the kgId.
UNWIND $docs AS doc
MERGE (f:FLOW {node_kg_id: doc.kgId})
SET f.node_complete     = true,
    f.node_name        = CASE
        WHEN doc.name IS NOT NULL AND doc.name <> '' THEN doc.name
        WHEN doc.flowType = 'COMPOSE_ENGINE'  THEN doc.feature + '-' + doc.operation
        WHEN doc.flowType = 'PROCESS_MANAGER' THEN last(split(doc.kgId, '--'))
        ELSE '' END,
    f.node_type        = 'FLOW',
    f.component_name   = coalesce(doc.metadata.repoName, ''),
    f.generated_from   = coalesce(doc.metadata.generatedFrom, ''),
    f.generated_at     = coalesce(doc.metadata.generatedAt, ''),
    f.version          = coalesce(doc.metadata.version, ''),
    f.flow_type        = coalesce(doc.flowType, ''),
    f.feature          = coalesce(doc.feature, ''),
    f.operation        = coalesce(doc.operation, ''),
    f.service_kg_id    = doc.serviceKgId
WITH f WHERE f.flow_type IS NOT NULL AND f.flow_type <> ''
CALL apoc.create.addLabels(f, [toString(f.flow_type)]) YIELD node AS _
RETURN count(*) AS total;

// --- 2. STATE processing nodes + CONSISTS_OF ---
UNWIND $docs AS doc
UNWIND coalesce(doc.processingNodes, []) AS pn
WITH doc, pn WHERE pn.type = 'State'
MERGE (f:FLOW {node_kg_id: doc.kgId})
MERGE (s:STATE {node_kg_id: pn.nodeId})
SET s.node_name        = pn.name,
    s.node_type        = 'STATE',
    s.node_complete     = true,
    s.component_name   = coalesce(doc.metadata.repoName, ''),
    s.generated_from   = coalesce(doc.metadata.generatedFrom, ''),
    s.generated_at     = coalesce(doc.metadata.generatedAt, ''),
    s.version          = coalesce(doc.metadata.version, ''),
    s.node_description  = coalesce(pn.props.state.description, ''),
    s.persist          = pn.props.state.persist,
    s.initiate_async   = pn.props.state.initiateAsync
WITH s, f
CALL apoc.create.addLabels(s,
  [l IN ['PERSISTENT'] WHERE s.persist        | l] +
  [l IN ['ASYNC']       WHERE s.initiate_async | l]
) YIELD node AS _
MERGE (f)-[:CONSISTS_OF]->(s);

// --- 3. ACTION processing nodes + CONSISTS_OF + INVOKES_FLOW (-> referenced CM flow) ---
UNWIND $docs AS doc
UNWIND coalesce(doc.processingNodes, []) AS pn
WITH doc, pn WHERE pn.type = 'Action'
MERGE (f:FLOW {node_kg_id: doc.kgId})
MERGE (a:ACTION {node_kg_id: pn.nodeId})
SET a.node_name         = pn.name,
    a.node_type         = 'ACTION',
    a.node_complete      = true,
    a.component_name    = coalesce(doc.metadata.repoName, ''),
    a.generated_from    = coalesce(doc.metadata.generatedFrom, ''),
    a.generated_at      = coalesce(doc.metadata.generatedAt, ''),
    a.version           = coalesce(doc.metadata.version, ''),
    a.action_type       = pn.props.action.type,
    a.feature           = pn.props.action.feature,
    a.operation         = pn.props.action.operation,
    a.component         = pn.props.action.component,
    a.mapper_identifier = pn.props.action.mapperIdentifier
WITH a, f, pn.props.action.`$ref` AS ref
CALL apoc.create.addLabels(a, [l IN [a.action_type] WHERE l IS NOT NULL AND l <> '' | toString(l)]) YIELD node AS _
MERGE (f)-[:CONSISTS_OF]->(a)
WITH a, ref
WHERE ref IS NOT NULL AND ref <> ''
WITH a, replace(last(split(ref, '/')), '.json', '') AS cmFlowKgId
WHERE cmFlowKgId <> ''
MERGE (cm:FLOW {node_kg_id: cmFlowKgId})
ON CREATE SET cm.node_type = 'FLOW', cm.node_complete = false
MERGE (a)-[:INVOKES_FLOW]->(cm);

// --- 4. CONDITION processing nodes + CONSISTS_OF ---
UNWIND $docs AS doc
UNWIND coalesce(doc.processingNodes, []) AS pn
WITH doc, pn WHERE pn.type = 'Condition'
MERGE (f:FLOW {node_kg_id: doc.kgId})
MERGE (c:CONDITION {node_kg_id: pn.nodeId})
SET c.node_name        = pn.name,
    c.node_type        = 'CONDITION',
    c.node_complete     = true,
    c.component_name   = coalesce(doc.metadata.repoName, ''),
    c.generated_from   = coalesce(doc.metadata.generatedFrom, ''),
    c.generated_at     = coalesce(doc.metadata.generatedAt, ''),
    c.version          = coalesce(doc.metadata.version, ''),
    c.expression       = pn.props.condition.expression
MERGE (f)-[:CONSISTS_OF]->(c);

// --- 5. BEHAVIOUR processing nodes -> BEHAVIOUR(LPU) + CONSISTS_OF ---
// Resolve to the LPU node (node_kg_id from props.behaviour.$ref). If that node does not yet
// exist we plant a minimal typed stub (node_kg_id + node_type only) — behaviour.cypher owns
// the real properties (node_name from the LPU's own `name`, sub_type, description, ...) and
// fills them in when it runs. ON CREATE only, so we never clobber what behaviour.cypher sets.
// Domain rule: PROCESS_MANAGER flows orchestrate only State/Action/Condition — Behaviour
// nodes belong to compose (COMPOSE_ENGINE) flows — so we never materialize them for PM flows.
UNWIND $docs AS doc
UNWIND coalesce(doc.processingNodes, []) AS pn
WITH doc, pn WHERE pn.type = 'Behaviour' AND doc.flowType = 'COMPOSE_ENGINE'
WITH doc, pn, replace(last(split(coalesce(pn.props.behaviour.`$ref`, ''), '/')), '.json', '') AS lpuKgId
WHERE lpuKgId <> ''
MERGE (f:FLOW {node_kg_id: doc.kgId})
MERGE (b:BEHAVIOUR {node_kg_id: lpuKgId})
ON CREATE SET b.node_type = 'BEHAVIOUR', b.node_complete = false
MERGE (f)-[:CONSISTS_OF]->(b);

// --- 6. TRANSITIONS_TO edges from flowPaths ---
UNWIND $docs AS doc
UNWIND keys(coalesce(doc.flowPaths, {})) AS pathKey
UNWIND doc.flowPaths[pathKey] AS step
WITH step.from.nodeId AS fromId, step.to.nodeId AS toId, pathKey, step
WHERE fromId IS NOT NULL AND fromId <> '' AND toId IS NOT NULL AND toId <> ''
MATCH (fromNode {node_kg_id: fromId})
MATCH (toNode   {node_kg_id: toId})
MERGE (fromNode)-[:TRANSITIONS_TO {path: pathKey, step: step.stepNumber}]->(toNode);
