// component.cypher — COMPONENT node ingestion from a single component KG JSON file.
// Parameters (supplied by load.py on every statement):
//   $docs — list containing one parsed component document
// No APOC required.
//
// Model:
//   (:COMPONENT) — root node representing a repository component
//   (:COMPONENT)-[:CONSISTS_OF]->(:SERVICE | :BEHAVIOUR | :FLOW | :SYNC | :DATA_ACCESS)
// node_kg_id = metadata.repoName — the key all child entities carry as component_name.
// Glossary stored as parallel lists (glossary_terms / glossary_meanings) because Neo4j
// does not support lists of maps as node properties.
// Run after all other entity cyphers: CONSISTS_OF edges rely on child nodes existing.

// --- 1. COMPONENT node ---
UNWIND $docs AS doc
MERGE (c:COMPONENT {node_kg_id: doc.metadata.repoName})
SET c.node_name         = coalesce(doc.componentName, ''),
    c.node_type         = 'COMPONENT',
    c.node_complete     = true,
    c.component_name    = coalesce(doc.metadata.repoName, ''),
    c.description       = coalesce(doc.description, ''),
    c.generated_at      = coalesce(doc.metadata.generatedAt, ''),
    c.generated_by      = coalesce(doc.metadata.generatedBy, ''),
    c.version           = coalesce(doc.metadata.version, ''),
    c.service_count     = doc.metadata.serviceCount,
    c.glossary_terms    = [g IN coalesce(doc.glossary, []) | g.term],
    c.glossary_meanings = [g IN coalesce(doc.glossary, []) | g.meaning]
RETURN count(*) AS total;
