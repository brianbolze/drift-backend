SELECT 
  b.bullet_diameter_inches as diameter,
  COUNT(DISTINCT c.id) as num_calibers,
  COUNT(DISTINCT b.id) as num_bullets,
  COUNT(DISTINCT cart.id) as num_cartridges
FROM bullet b
LEFT JOIN caliber c ON b.bullet_diameter_inches = c.bullet_diameter_inches
LEFT JOIN cartridge cart ON c.id = cart.caliber_id
GROUP BY b.bullet_diameter_inches
ORDER BY b.bullet_diameter_inches;