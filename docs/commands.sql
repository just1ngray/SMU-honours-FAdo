-- Select distinct non-error re_math rows (export)
SELECT *
FROM (
	SELECT *, ROW_NUMBER() OVER(PARTITION BY re_math ORDER BY url ASC, lineNum ASC) rn
	FROM expressions
	WHERE re_math NOT LIKE '%Error%'
) a
WHERE rn=1
ORDER BY re_math ASC;



-- Statistics --
SELECT lang, ntotal, ndistinct
FROM (
	-- main content --
	SELECT 0 as rn, lang, count(re_math) as ntotal, count(DISTINCT re_math) as ndistinct
	FROM expressions
	WHERE re_math NOT LIKE '%Error%'
	GROUP BY lang

	-- blank line --
	UNION SELECT 1 as rn, '', '', ''

	-- total row --
	UNION SELECT 2 as rn, 'Total', count(re_math), count(DISTINCT re_math)
	FROM expressions
	WHERE re_math NOT LIKE '%Error%'

	ORDER BY rn ASC, ntotal DESC
);