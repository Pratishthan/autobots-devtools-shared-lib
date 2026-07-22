// constraints.cypher — all KG node uniqueness constraints.
// Run once before any data ingestion:
//   python load.py --cypher cypher/constraints.cypher
// No data file required; schema statements carry no $doc/$fileName references.

CREATE CONSTRAINT IF NOT EXISTS FOR (b:BEHAVIOUR)           REQUIRE b.node_kg_id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (s:DATA_MODEL)          REQUIRE s.node_kg_id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (p:DATA_MODEL_PROPERTY) REQUIRE p.node_kg_id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (f:FLOW)                REQUIRE f.node_kg_id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (s:STATE)               REQUIRE s.node_kg_id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (a:ACTION)              REQUIRE a.node_kg_id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (c:CONDITION)           REQUIRE c.node_kg_id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (d:DATA_ACCESS)         REQUIRE d.node_kg_id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (s:SYNC)                REQUIRE s.node_kg_id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (s:SERVICE)             REQUIRE s.node_kg_id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (c:COMPONENT)           REQUIRE c.node_kg_id IS UNIQUE;
