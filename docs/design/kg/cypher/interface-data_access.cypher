// interface-data_access.cypher — DATA_ACCESS ingestion from data-access JSON files (bulk).
// Parameters (supplied by load.py on every statement):
//   $docs — list of file documents; each element is an object with a metadata section and
//           a fetchMethods list. Outer UNWIND iterates files, inner UNWIND iterates entries.
// Requires APOC: apoc.create.addLabels.
//

// DATA_ACCESS -[:QUERIES]-> DATA_MODEL is intentionally NOT created here: the data-access
// JSON carries no modelKgId. That edge is established by behaviour.cypher, whose LPU
// dataReaders[] pair each dataAccessKgId with its modelKgId.

// --- 1. DATA_ACCESS nodes ---
// domain is read off the kgId segments (repo--DataAccess--<domain>--<method>).
// return_type derives from the singleResponse flag.
UNWIND $docs AS doc
UNWIND coalesce(doc.repoMethods, []) AS da
WITH doc, da WHERE da.dataAccessKgId IS NOT NULL AND da.dataAccessKgId <> ''
MERGE (d:DATA_ACCESS {node_kg_id: da.dataAccessKgId})
SET d.node_name        = da.fetchMethod,
    d.node_type        = 'DATA_ACCESS',
    d.node_complete     = true,
    d.component_name   = coalesce(doc.metadata.repoName, ''),
    d.domain           = split(da.dataAccessKgId, '--')[2],
    d.generated_from   = coalesce(doc.metadata.generatedFrom, ''),
    d.generated_at     = coalesce(doc.metadata.generatedAt, ''),
    d.version          = coalesce(doc.metadata.version, ''),
    d.node_description  = coalesce(da.description, ''),
    d.query            = coalesce(da.query, ''),
    d.return_type      = CASE WHEN da.singleResponse THEN 'SINGLE' ELSE 'LIST' END,
    d.parameters       = [p IN coalesce(da.fetchParams, []) | p.fetchParamsName + ': ' + p.fetchParamsType]
WITH d WHERE d.return_type IS NOT NULL
CALL apoc.create.addLabels(d, [d.return_type]) YIELD node AS _
RETURN count(*) AS total;
