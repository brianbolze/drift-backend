-- Facet summary pivoted by popular calibers
-- product_line is prefixed with manufacturer name for self-descriptive labels
WITH calibers AS (
  SELECT id, name, bullet_diameter_inches AS diam
  FROM caliber
  WHERE name IN (
    '6.5 Creedmoor', '.308 Winchester',
    '6mm Dasher', '5.56x45mm NATO', '.22 Long Rifle'
  )
),
bullet_tags AS (
  SELECT cal.name AS caliber, 'type_tags' AS facet, j.value AS value, b.id AS bullet_id
  FROM bullet b
  JOIN calibers cal ON b.bullet_diameter_inches = cal.diam
  JOIN json_each(b.type_tags) AS j
  UNION ALL
  SELECT cal.name, 'used_for', j.value, b.id
  FROM bullet b
  JOIN calibers cal ON b.bullet_diameter_inches = cal.diam
  JOIN json_each(b.used_for) AS j
),
bullet_scalars AS (
  SELECT cal.name AS caliber, 'base_type' AS facet, b.base_type AS value, b.id AS bullet_id
  FROM bullet b
  JOIN calibers cal ON b.bullet_diameter_inches = cal.diam
  WHERE b.base_type IS NOT NULL
  UNION ALL
  SELECT cal.name, 'tip_type', b.tip_type, b.id
  FROM bullet b
  JOIN calibers cal ON b.bullet_diameter_inches = cal.diam
  WHERE b.tip_type IS NOT NULL
  UNION ALL
  SELECT cal.name, 'product_line', m.short_name || ' ' || b.product_line, b.id
  FROM bullet b
  JOIN calibers cal ON b.bullet_diameter_inches = cal.diam
  JOIN manufacturer m ON b.manufacturer_id = m.id
  WHERE b.product_line IS NOT NULL
),
combined AS (
  SELECT * FROM bullet_tags
  UNION ALL
  SELECT * FROM bullet_scalars
)
SELECT
  facet,
  value,
  COUNT(DISTINCT CASE WHEN caliber = '6.5 Creedmoor'    THEN bullet_id END) AS "6.5 CM",
  COUNT(DISTINCT CASE WHEN caliber = '.308 Winchester'   THEN bullet_id END) AS ".308 Win",
  COUNT(DISTINCT CASE WHEN caliber = '6mm Dasher'        THEN bullet_id END) AS "6mm Dash",
  COUNT(DISTINCT CASE WHEN caliber = '5.56x45mm NATO'    THEN bullet_id END) AS "5.56 NATO",
  COUNT(DISTINCT CASE WHEN caliber = '.22 Long Rifle'    THEN bullet_id END) AS ".22 LR",
  COUNT(DISTINCT bullet_id) AS total
FROM combined
GROUP BY facet, value
ORDER BY facet, total DESC;