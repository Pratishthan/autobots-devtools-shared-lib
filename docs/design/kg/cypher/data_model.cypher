// data_model.cypher — DATA_MODEL / DATA_MODEL_PROPERTY ingestion from OpenAPI JSON files (bulk).
// Parameters (supplied by load.py on every statement):
//   $docs — list of parsed OpenAPI documents, one element per input file
// Requires APOC: apoc.map.removeKeys, apoc.map.fromPairs, apoc.meta.cypher.isType, apoc.create.addLabels.

// --- 1. DATA_MODEL nodes ---
UNWIND $docs AS doc
WITH doc, doc.info AS info
WITH info, doc, keys(coalesce(doc.components.schemas, {})) AS schemaNames
UNWIND schemaNames AS schemaName
WITH doc, info, schemaName, doc.components.schemas[schemaName] AS schemaDef,
     coalesce(doc.components.schemas[schemaName].`x-fbp-params`, {}) AS fbp
MERGE (s:DATA_MODEL {node_kg_id: coalesce(fbp.kgId, schemaName)})
SET s.node_name        = schemaName,
    s.node_type        = 'DATA_MODEL',
    s.node_complete     = true,
    s.api_title        = coalesce(info.title, ''),
    s.api_version      = coalesce(info.version, ''),
    s.component_name   = coalesce(fbp.repoName, ''),
    s.generated_from   = coalesce(fbp.generatedFrom, ''),
    s.generated_at     = coalesce(fbp.generatedAt, ''),
    s.version          = coalesce(fbp.version, ''),
    s.node_description = coalesce(schemaDef.description, '')
SET s += apoc.map.removeKeys(fbp, ['kgId', 'repoName', 'node_complete', 'repo', 'version', 'generatedAt']);

// --- 2. DATA_MODEL_PROPERTY nodes + HAS_PROPERTY ---
UNWIND $docs AS doc
WITH doc, keys(coalesce(doc.components.schemas, {})) AS schemaNames
UNWIND schemaNames AS schemaName
WITH doc, schemaName, doc.components.schemas[schemaName] AS schemaDef,
     coalesce(doc.components.schemas[schemaName].`x-fbp-params`.kgId, schemaName) AS modelKgId,
     coalesce(doc.components.schemas[schemaName].`x-fbp-params`.repoName, '') AS componentName,
     coalesce(doc.components.schemas[schemaName].`x-fbp-params`.generatedAt, '') AS schemaGeneratedAt,
     coalesce(doc.components.schemas[schemaName].`x-fbp-params`.version, '') AS schemaVersion,
     coalesce(doc.components.schemas[schemaName].`x-fbp-params`.generatedFrom, '') AS schemaGeneratedFrom,
     coalesce(doc.components.schemas[schemaName].required, []) AS requiredFields
WITH doc, modelKgId, componentName, schemaGeneratedAt, schemaVersion, schemaGeneratedFrom, requiredFields, schemaDef, keys(coalesce(schemaDef.properties, {})) AS propNames
UNWIND propNames AS propName
WITH doc, modelKgId, componentName, schemaGeneratedAt, schemaVersion, schemaGeneratedFrom, requiredFields, propName, schemaDef.properties[propName] AS propDef,
     coalesce(schemaDef.properties[propName].`x-fbp-params`, {}) AS pfbp,
     schemaDef.properties[propName].`$ref` AS refPath
MERGE (s:DATA_MODEL {node_kg_id: modelKgId})
MERGE (p:DATA_MODEL_PROPERTY {node_kg_id:
        coalesce(pfbp.propertyKgId, modelKgId + '--Property--' + propName)})
SET p.node_name           = propName,
    p.node_type           = 'DATA_MODEL_PROPERTY',
    p.node_complete        = true,
    p.component_name      = componentName,
    p.generated_from      = schemaGeneratedFrom,
    p.generated_at        = schemaGeneratedAt,
    p.version             = schemaVersion,
    p.data_type           = CASE WHEN refPath IS NOT NULL THEN 'reference'
                                 ELSE coalesce(propDef.type, '') END,
    p.required            = propName IN requiredFields,
    p.min_length          = propDef.minLength,
    p.default_value       = CASE WHEN propDef.default IS NULL THEN null
                                 ELSE toString(propDef.default) END,
    p.node_description    = coalesce(propDef.description, ''),
    p.ref_path            = refPath,
    p.property_type_kg_id = pfbp.propertyTypeKgId
SET p += apoc.map.fromPairs([
        key IN keys(propDef)
        WHERE NOT key IN ['type', 'description', 'minLength', 'default', '$ref', 'x-fbp-params', 'node_complete']
          AND NOT apoc.meta.cypher.isType(propDef[key], 'MAP')
          AND NOT apoc.meta.cypher.isType(propDef[key], 'LIST OF MAP')
        | [key, propDef[key]]
    ])
WITH p, s
CALL apoc.create.addLabels(p,
  [l IN ['REFERENCE'] WHERE p.data_type = 'reference' | l] +
  [l IN ['REQUIRED']  WHERE p.required  = true         | l]
) YIELD node AS _
MERGE (s)-[:HAS_PROPERTY]->(p);

// --- 3. IS_OF_TYPE relationships for $ref properties ---
UNWIND $docs AS doc
WITH doc, keys(coalesce(doc.components.schemas, {})) AS schemaNames
UNWIND schemaNames AS schemaName
WITH doc, schemaName, doc.components.schemas[schemaName] AS schemaDef,
     coalesce(doc.components.schemas[schemaName].`x-fbp-params`.kgId, schemaName) AS modelKgId
WITH modelKgId, schemaDef, keys(coalesce(schemaDef.properties, {})) AS propNames
UNWIND propNames AS propName
WITH coalesce(schemaDef.properties[propName].`x-fbp-params`.propertyKgId,
              modelKgId + '--Property--' + propName) AS propNodeKgId,
     schemaDef.properties[propName].`x-fbp-params`.propertyTypeKgId AS refId,
     schemaDef.properties[propName].`$ref` AS refPath
WHERE refPath IS NOT NULL AND refId IS NOT NULL
MERGE (p:DATA_MODEL_PROPERTY {node_kg_id: propNodeKgId})
MERGE (ref:DATA_MODEL {node_kg_id: refId})
ON CREATE SET ref.node_type = 'DATA_MODEL', ref.node_complete = false
MERGE (p)-[:IS_OF_TYPE]->(ref);
