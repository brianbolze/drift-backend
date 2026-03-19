-- DB Overview: row counts across all core tables
SELECT 'manufacturer'    AS tbl, COUNT(*) AS rows FROM manufacturer
UNION ALL SELECT 'caliber',        COUNT(*) FROM caliber
UNION ALL SELECT 'chamber',        COUNT(*) FROM chamber
UNION ALL SELECT 'bullet',         COUNT(*) FROM bullet
UNION ALL SELECT 'bullet_bc_source', COUNT(*) FROM bullet_bc_source
UNION ALL SELECT 'cartridge',      COUNT(*) FROM cartridge
UNION ALL SELECT 'rifle_model',    COUNT(*) FROM rifle_model
UNION ALL SELECT 'optic',          COUNT(*) FROM optic
UNION ALL SELECT 'entity_alias',   COUNT(*) FROM entity_alias;