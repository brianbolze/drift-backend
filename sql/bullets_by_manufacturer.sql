-- Bullets per manufacturer, with BC coverage stats
SELECT
    m.name                                                  AS manufacturer,
    COUNT(*)                                                AS bullet_count,
    SUM(CASE WHEN b.bc_g7_published IS NOT NULL THEN 1 ELSE 0 END) AS has_g7,
    SUM(CASE WHEN b.bc_g1_published IS NOT NULL THEN 1 ELSE 0 END) AS has_g1,
    SUM(CASE WHEN b.bc_g7_published IS NULL AND b.bc_g1_published IS NULL THEN 1 ELSE 0 END) AS no_bc,
    SUM(b.is_locked)                                        AS locked
FROM bullet b
JOIN manufacturer m ON b.manufacturer_id = m.id
GROUP BY m.name
ORDER BY bullet_count DESC;
