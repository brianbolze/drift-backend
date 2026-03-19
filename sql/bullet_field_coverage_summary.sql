-- How populated is each filterable field?
SELECT
  COUNT(*) AS total_bullets,
  SUM(CASE WHEN type_tags IS NOT NULL AND type_tags <> '[]' THEN 1 ELSE 0 END) AS has_type_tags,    -- 1265/1284
  SUM(CASE WHEN used_for IS NOT NULL AND used_for <> '[]' THEN 1 ELSE 0 END)  AS has_used_for,      -- 1272/1284
  SUM(CASE WHEN base_type IS NOT NULL THEN 1 ELSE 0 END)  AS has_base_type,    -- 832/1284
  SUM(CASE WHEN tip_type IS NOT NULL THEN 1 ELSE 0 END)   AS has_tip_type,     -- 909/1284
  SUM(CASE WHEN product_line IS NOT NULL THEN 1 ELSE 0 END) AS has_product_line -- 738/1284
FROM bullet;
