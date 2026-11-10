-- Convenience views and macros (created after the data is loaded).

-- One row per (observation, dimension): the MAP column unnested.
CREATE VIEW observation_dims AS
SELECT table_id, obs_id, e.key AS dim_code, e.value AS value_code
FROM (SELECT table_id, obs_id, unnest(map_entries(dims)) AS e FROM observations);

-- Full path of every topic in each language, e.g. 'Economy and finances / Consumer Prices'.
CREATE VIEW topic_paths AS
WITH RECURSIVE p AS (
    SELECT topic_id, parent_id, level, code,
           name_hy AS path_hy, name_en AS path_en, name_ru AS path_ru
    FROM topics WHERE parent_id IS NULL
    UNION ALL
    SELECT t.topic_id, t.parent_id, t.level, t.code,
           p.path_hy || ' / ' || t.name_hy,
           p.path_en || ' / ' || t.name_en,
           p.path_ru || ' / ' || t.name_ru
    FROM topics t JOIN p ON t.parent_id = p.topic_id
)
SELECT * FROM p;

-- Catalogue: one row per table with its primary topic path.
CREATE VIEW catalog AS
SELECT d.table_id,
       tp.code AS topic_code,
       tp.path_hy AS topic_hy, tp.path_en AS topic_en, tp.path_ru AS topic_ru,
       d.title_hy, d.title_en, d.title_ru,
       d.unit_hy, d.unit_en, d.unit_ru,
       d.first_period, d.last_period, d.updated,
       d.n_dimensions, d.n_cells, d.n_values,
       d.en_origin, d.url_en, d.url_hy, d.ckan_url
FROM datasets d
JOIN dataset_topics dt ON dt.table_id = d.table_id AND dt.is_primary
JOIN topic_paths tp ON tp.topic_id = dt.topic_id;

-- Long format with labels in all three languages: one row per (observation, dimension).
CREATE VIEW data_long AS
SELECT od.table_id, od.obs_id,
       d.position AS dim_position, od.dim_code,
       d.label_hy AS dim_label_hy, d.label_en AS dim_label_en, d.label_ru AS dim_label_ru,
       od.value_code,
       v.label_hy AS value_label_hy, v.label_en AS value_label_en, v.label_ru AS value_label_ru,
       v.period AS value_period, o.period,
       o.value, o.status
FROM observation_dims od
JOIN observations o USING (table_id, obs_id)
JOIN dimensions d ON d.table_id = od.table_id AND d.dim_code = od.dim_code
JOIN dimension_values v
  ON v.table_id = od.table_id AND v.dim_code = od.dim_code AND v.value_code = od.value_code;

-- One row per observation, labels as MAP {dim_code: label} in a chosen language.
-- Missing labels fall back to English, then to the code.
CREATE MACRO table_data(tid, lang := 'en') AS TABLE
SELECT o.table_id, o.obs_id,
       map_from_entries(list((d.dim_code,
           coalesce(CASE lang WHEN 'hy' THEN v.label_hy WHEN 'ru' THEN v.label_ru END,
                    v.label_en, v.value_code))
           ORDER BY d.position)) AS labels,
       o.dims, o.period, o.value, o.status
FROM observations o
JOIN dimensions d ON d.table_id = o.table_id
JOIN dimension_values v
  ON v.table_id = o.table_id AND v.dim_code = d.dim_code AND v.value_code = o.dims[d.dim_code]
WHERE o.table_id = tid
GROUP BY o.table_id, o.obs_id, o.dims, o.period, o.value, o.status
ORDER BY o.obs_id;

-- Long format for one table in one language; easy to PIVOT into a wide table:
--   PIVOT (FROM table_long('AF-1-2024', lang := 'ru'))
--   ON dimension USING first(label) GROUP BY obs_id, value, status;
CREATE MACRO table_long(tid, lang := 'en') AS TABLE
SELECT o.table_id, o.obs_id, d.position AS dim_position, d.dim_code,
       coalesce(CASE lang WHEN 'hy' THEN d.label_hy WHEN 'ru' THEN d.label_ru END,
                    d.label_en, d.dim_code)
           AS dimension,
       v.value_code,
       coalesce(CASE lang WHEN 'hy' THEN v.label_hy WHEN 'ru' THEN v.label_ru END,
                    v.label_en, v.value_code)
           AS label,
       o.period, o.value, o.status
FROM observations o
JOIN dimensions d ON d.table_id = o.table_id
JOIN dimension_values v
  ON v.table_id = o.table_id AND v.dim_code = d.dim_code AND v.value_code = o.dims[d.dim_code]
WHERE o.table_id = tid
ORDER BY o.obs_id, d.position;

-- Share of texts available per language (for monitoring translation coverage).
CREATE VIEW translation_coverage AS
SELECT 'topics' AS entity, count(*) AS n,
       count(name_hy) AS hy, count(name_en) AS en, count(name_ru) AS ru,
       count(*) FILTER (WHERE en_machine) AS en_machine
FROM topics
UNION ALL
SELECT 'datasets.title', count(*), count(title_hy), count(title_en), count(title_ru),
       count(*) FILTER (WHERE en_origin = 'machine')
FROM datasets
UNION ALL
SELECT 'dimensions', count(*), count(label_hy), count(label_en), count(label_ru),
       count(*) FILTER (WHERE en_machine)
FROM dimensions
UNION ALL
SELECT 'dimension_values', count(*), count(label_hy), count(label_en), count(label_ru),
       count(*) FILTER (WHERE en_machine)
FROM dimension_values;
