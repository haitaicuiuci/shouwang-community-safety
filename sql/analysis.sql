-- name: split_distribution
SELECT split, source_label, COUNT(*) AS n FROM samples GROUP BY split,source_label ORDER BY split,source_label;
-- name: quality_exclusions
SELECT reason, COUNT(*) AS n FROM quality_exclusions GROUP BY reason;
-- name: confusion_matrix
SELECT p.strategy,s.source_label AS truth,p.prediction,COUNT(*) AS n FROM predictions p JOIN samples s ON s.id=p.sample_id WHERE p.strategy!='cascade' GROUP BY p.strategy,s.source_label,p.prediction;
-- name: route_coverage
SELECT decision,COUNT(*) AS n,ROUND(1.0*COUNT(*)/(SELECT COUNT(*) FROM predictions WHERE strategy='cascade'),6) AS share_of_all_test FROM predictions WHERE strategy='cascade' GROUP BY decision;
-- name: risk_errors
SELECT s.policy_risk,COUNT(*) AS n,SUM(s.source_label=1 AND p.prediction=0) AS fn,SUM(s.source_label=0 AND p.prediction=1) AS fp FROM predictions p JOIN samples s ON s.id=p.sample_id WHERE p.strategy='lightweight' GROUP BY s.policy_risk;
-- name: route_errors
SELECT p.decision,COUNT(*) AS n,SUM(s.source_label=1) AS labeled_offensive,SUM(s.source_label=0) AS labeled_safe FROM predictions p JOIN samples s ON s.id=p.sample_id WHERE p.strategy='cascade' GROUP BY p.decision;
-- name: queue_workload
SELECT reason,COUNT(*) AS pending FROM review_queue GROUP BY reason;
-- name: cross_split_leakage
SELECT normalized_hash,COUNT(DISTINCT split) AS split_count FROM samples GROUP BY normalized_hash HAVING split_count>1;
-- name: topic_errors
SELECT s.topic,COUNT(*) AS n,SUM(s.source_label=1 AND p.prediction=0) AS fn,SUM(s.source_label=0 AND p.prediction=1) AS fp FROM predictions p JOIN samples s ON s.id=p.sample_id WHERE p.strategy='lightweight' GROUP BY s.topic;
