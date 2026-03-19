-- Product lines grouped by manufacturer, with bullet count
SELECT m.name AS manufacturer, b.product_line, COUNT(*) AS bullet_count
FROM bullet b
JOIN manufacturer m ON b.manufacturer_id = m.id
WHERE b.product_line IS NOT NULL
GROUP BY m.name, b.product_line
ORDER BY m.name, bullet_count DESC;
