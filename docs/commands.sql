-- Select distinct non-error re rows
SELECT *
FROM (
	SELECT *, ROW_NUMBER() OVER(PARTITION BY re_math ORDER BY url ASC, lineNum ASC) rn
	FROM expressions
	WHERE re_math NOT LIKE '%Error%'
) a
WHERE rn=1
ORDER BY re_math ASC;


-- Count distinct non-error re rows by language
SELECT lang, count(DISTINCT re_math)
FROM expressions
WHERE re_math NOT LIKE '%Error%'
GROUP BY lang;