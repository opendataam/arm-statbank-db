-- armstat-db schema (DuckDB)
--
-- Conventions
--   * Every human-readable text exists in three columns: *_hy (Armenian), *_en (English),
--     *_ru (Russian). Armenian and English come from Armstat; Russian is always a machine
--     translation; English is a machine translation only where Armstat has none
--     (see the en_machine flags and the translations table).
--   * Codes (table_id, dim_code, value_code) are the PXWeb codes and are identical in the
--     Armenian and English interfaces of Statbank.

CREATE TABLE build_info (
    key   VARCHAR PRIMARY KEY,
    value VARCHAR
);

CREATE TABLE languages (
    lang        VARCHAR PRIMARY KEY,   -- ISO 639-1: hy, en, ru
    name_hy     VARCHAR NOT NULL,
    name_en     VARCHAR NOT NULL,
    name_ru     VARCHAR NOT NULL,
    origin      VARCHAR NOT NULL       -- 'armstat' (official) | 'mixed' | 'machine'
);

-- Navigation tree of Statbank (sections and sub-sections).
CREATE TABLE topics (
    topic_id    VARCHAR PRIMARY KEY,   -- API folder path, e.g. '1 Econnomy and finance/12 Consumer Prices'
    parent_id   VARCHAR,               -- NULL for the 8 top-level sections
    level       TINYINT NOT NULL,      -- 1 = section
    position    SMALLINT NOT NULL,     -- order among siblings, as on the site
    code        VARCHAR,               -- numbering taken from the name, e.g. '1.2'
    name_hy     VARCHAR,
    name_en     VARCHAR,
    name_ru     VARCHAR,
    en_machine  BOOLEAN NOT NULL DEFAULT FALSE,
    n_tables    INTEGER                -- tables directly in this folder
);

-- One row per statistical table (PX matrix).
CREATE TABLE datasets (
    table_id            VARCHAR PRIMARY KEY,  -- PX file id, e.g. 'EF-cpi-mi1'
    matrix              VARCHAR,              -- PX MATRIX keyword
    subject_code        VARCHAR,
    title_hy            VARCHAR,              -- full title (PX DESCRIPTION)
    title_en            VARCHAR,
    title_ru            VARCHAR,
    contents_hy         VARCHAR,              -- short subject (PX CONTENTS)
    contents_en         VARCHAR,
    contents_ru         VARCHAR,
    unit_hy             VARCHAR,
    unit_en             VARCHAR,
    unit_ru             VARCHAR,
    decimals            TINYINT,
    subject_area_hy     VARCHAR,
    subject_area_en     VARCHAR,
    subject_area_ru     VARCHAR,
    source_hy           VARCHAR,              -- data source (HTML removed)
    source_en           VARCHAR,
    source_ru           VARCHAR,
    source_link         VARCHAR,              -- first hyperlink found in the source
    note_hy             VARCHAR,              -- footnotes, newline-separated
    note_en             VARCHAR,
    note_ru             VARCHAR,
    updated             TIMESTAMPTZ,          -- last update at Armstat
    official_statistics BOOLEAN,
    n_dimensions        TINYINT NOT NULL,
    n_cells             INTEGER NOT NULL,     -- product of dimension sizes
    n_values            INTEGER NOT NULL,     -- non-missing cells
    first_period        VARCHAR,              -- min/max of the time dimension, if any
    last_period         VARCHAR,
    stub                VARCHAR[],            -- dim_codes shown as rows on the site
    heading             VARCHAR[],            -- dim_codes shown as columns on the site
    en_origin           VARCHAR NOT NULL,     -- 'armstat' | 'partial' | 'machine'
    hy_available        BOOLEAN NOT NULL,     -- Armenian metadata found in the API
    api_path            VARCHAR NOT NULL,     -- path under /api/v1/{lang}/ArmStatBank/
    url_hy              VARCHAR,
    url_en              VARCHAR,
    ckan_name           VARCHAR,              -- dataset on data.opendata.am
    ckan_url            VARCHAR
);

-- A table can be published in more than one folder (e.g. EF-gf-3).
CREATE TABLE dataset_topics (
    table_id    VARCHAR NOT NULL REFERENCES datasets (table_id),
    topic_id    VARCHAR NOT NULL REFERENCES topics (topic_id),
    api_path    VARCHAR NOT NULL,
    is_primary  BOOLEAN NOT NULL,
    PRIMARY KEY (table_id, topic_id)
);

-- Dimensions (PX variables) of each table, without the technical ContentsCode.
CREATE TABLE dimensions (
    table_id    VARCHAR NOT NULL REFERENCES datasets (table_id),
    dim_code    VARCHAR NOT NULL,
    position    TINYINT NOT NULL,      -- 0-based order; defines obs_id layout
    placement   VARCHAR,               -- 'stub' (rows) | 'heading' (columns)
    is_time     BOOLEAN NOT NULL,
    elimination BOOLEAN,               -- PXWeb: may be omitted from a query
    label_hy    VARCHAR,
    label_en    VARCHAR,
    label_ru    VARCHAR,
    en_machine  BOOLEAN NOT NULL DEFAULT FALSE,
    n_values    INTEGER NOT NULL,
    PRIMARY KEY (table_id, dim_code)
);

-- Values (PX value codes and texts) of each dimension.
CREATE TABLE dimension_values (
    table_id    VARCHAR NOT NULL,
    dim_code    VARCHAR NOT NULL,
    value_code  VARCHAR NOT NULL,
    position    INTEGER NOT NULL,      -- 0-based order inside the dimension
    label_hy    VARCHAR,
    label_en    VARCHAR,
    label_ru    VARCHAR,
    en_machine  BOOLEAN NOT NULL DEFAULT FALSE,
    period      VARCHAR,               -- normalised period for time dimensions: 2015, 2015-Q1, 2015-03, --03
    year        SMALLINT,
    PRIMARY KEY (table_id, dim_code, value_code),
    FOREIGN KEY (table_id, dim_code) REFERENCES dimensions (table_id, dim_code)
);

-- Symbols used instead of missing values.
CREATE TABLE status_symbols (
    symbol          VARCHAR PRIMARY KEY,
    meaning_hy      VARCHAR NOT NULL,
    meaning_en      VARCHAR NOT NULL,
    meaning_ru      VARCHAR NOT NULL
);

-- Data cells. obs_id is the row-major index over the dimensions in `position` order
-- (the JSON-stat value index), so every combination of value codes appears once.
CREATE TABLE observations (
    table_id    VARCHAR NOT NULL REFERENCES datasets (table_id),
    obs_id      INTEGER NOT NULL,
    dims        MAP(VARCHAR, VARCHAR) NOT NULL,  -- {dim_code: value_code}
    period      VARCHAR,                         -- combined time period: 2015, 2015-Q1, 2015-03
    value       DOUBLE,                          -- NULL when missing, see status
    status      VARCHAR REFERENCES status_symbols (symbol),
    PRIMARY KEY (table_id, obs_id)
);

-- Translation memory used for every machine-translated text in the database.
CREATE TABLE translations (
    src_lang    VARCHAR NOT NULL,
    tgt_lang    VARCHAR NOT NULL,
    source      VARCHAR NOT NULL,
    target      VARCHAR NOT NULL,
    engine      VARCHAR,               -- model / tool that produced the translation
    reviewed    BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (src_lang, tgt_lang, source)
);
