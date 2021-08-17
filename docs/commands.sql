-- Select distinct non-error re rows
SELECT *
FROM (
	SELECT *, ROW_NUMBER() OVER(PARTITION BY re ORDER BY url ASC, lineNum ASC) rn
	FROM expressions
	WHERE re NOT LIKE '%Error%'
) a
WHERE rn=1
ORDER BY re ASC;


-- Count distinct non-error re rows by language
SELECT lang, count(DISTINCT re)
FROM expressions
WHERE re NOT LIKE '%Error%'
GROUP BY lang;