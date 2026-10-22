PRAGMA foreign_keys=ON;
CREATE TABLE samples(id TEXT PRIMARY KEY, source_row INTEGER, source_split TEXT, split TEXT CHECK(split IN ('train','validation','test')), text TEXT NOT NULL, normalized_hash TEXT UNIQUE, source_label INTEGER CHECK(source_label IN (0,1)), fine_label INTEGER, topic TEXT, policy_risk TEXT);
CREATE TABLE quality_exclusions(id TEXT, reason TEXT, retained_id TEXT);
CREATE TABLE predictions(sample_id TEXT REFERENCES samples(id), strategy TEXT, score REAL, prediction INTEGER, decision TEXT, rule_hit INTEGER, policy_version TEXT, PRIMARY KEY(sample_id,strategy));
CREATE TABLE review_queue(sample_id TEXT PRIMARY KEY REFERENCES samples(id), priority REAL, reason TEXT, status TEXT DEFAULT 'pending', policy_version TEXT);
CREATE TABLE experiment_metadata(key TEXT PRIMARY KEY, value TEXT);
