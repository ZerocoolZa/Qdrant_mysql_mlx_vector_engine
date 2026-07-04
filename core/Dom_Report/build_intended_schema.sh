#!/bin/bash
# Build the intended diagnostic_kb schema from the pre-Devin dump + 3 new tables
# Output: diagnostic_kb_intended_schema.sql

DUMP="/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Report/saved_sessions/diagnostic_kb_full_dump.sql"
OUT="/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Report/diagnostic_kb_intended_schema.sql"

echo "-- diagnostic_kb intended schema" > "$OUT"
echo "-- Reconstructed from pre-Devin dump (Jul 3 00:05) + architectural evolution" >> "$OUT"
echo "-- 49 tables: 9 authorities + 15 entities + 13 joins + 4 governance + 4 meta + 2 legacy + 3 new" >> "$OUT"
echo "-- No foundation_law (replaced by law/pattern/pattern_law/decision)" >> "$OUT"
echo "-- No question_type (replaced by type FK)" >> "$OUT"
echo "-- No chat_message (pollution)" >> "$OUT"
echo "-- entity + relation + RelationLink added (valid evolution)" >> "$OUT"
echo "" >> "$OUT"
echo "SET FOREIGN_KEY_CHECKS=0;" >> "$OUT"
echo "SET UNIQUE_CHECKS=0;" >> "$OUT"
echo "" >> "$OUT"

# Extract all CREATE TABLE + INSERT statements from the dump (the real pre-Devin state)
# Skip foundation_law and question_type
awk '
/^CREATE TABLE.*`foundation_law`/ {skip=1}
/^CREATE TABLE.*`question_type`/ {skip=1}
skip && /^) ENGINE/ {skip=0; next}
skip {next}
/^CREATE TABLE/,/^) ENGINE/ {print; if(/^) ENGINE/) print ""}
/^INSERT INTO `foundation_law`/ {next}
/^INSERT INTO `question_type`/ {next}
/^INSERT INTO/ {print}
' "$DUMP" >> "$OUT"

# Add the 3 new tables (entity, relation, RelationLink)
cat >> "$OUT" << 'SQLEOF'

-- ════════════════════════════════════════════════════════════════
-- NEW AUTHORITY TABLES (architectural evolution)
-- ════════════════════════════════════════════════════════════════

-- ─── ENTITY (authority — what something IS) ─────────────────────
CREATE TABLE `entity` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `table_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_entity_name` (`name`),
  UNIQUE KEY `uq_entity_table` (`table_name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `entity` VALUES
(1,'question','question',NOW()),
(2,'answer','answer',NOW()),
(3,'error','error',NOW()),
(4,'rule','rule',NOW()),
(5,'fact','fact',NOW()),
(6,'evidence','evidence',NOW()),
(7,'incident','incident',NOW()),
(8,'cause','cause',NOW()),
(9,'fix','fix',NOW()),
(10,'prevention','prevention',NOW()),
(11,'problem','problem',NOW()),
(12,'report','report',NOW()),
(13,'method','Method',NOW()),
(14,'computationunit','ComputationUnit',NOW()),
(15,'class','Class',NOW());

-- ─── RELATION (authority — how things connect) ──────────────────
CREATE TABLE `relation` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `is_directed` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_relation_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO `relation` VALUES
(1,'complement','Yin/yang — every question has a complementary question',1,NOW()),
(2,'contradiction','Two things that cannot both be true',1,NOW()),
(3,'refinement','A more specific version of a general concept',1,NOW()),
(4,'prerequisite','Must exist before the target can exist',1,NOW()),
(5,'broader','A more general version of a specific concept',1,NOW()),
(6,'consequence','Follows from the source',1,NOW()),
(7,'supports','Provides evidence for',1,NOW()),
(8,'challenges','Provides evidence against',1,NOW()),
(9,'depends','Requires the target to function',1,NOW()),
(10,'calls','Invokes the target',1,NOW()),
(11,'contains','Has the target as a member',1,NOW()),
(12,'references','Mentions or points to the target',1,NOW()),
(13,'inherits','Derives from the target',1,NOW()),
(14,'uses','Utilizes the target',1,NOW());

-- ─── RELATIONLINK (universal relationship table — replaces 5 specialized ones) ─
CREATE TABLE `RelationLink` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `source_entity` int NOT NULL,
  `source_id` bigint NOT NULL,
  `target_entity` int NOT NULL,
  `target_id` bigint NOT NULL,
  `relation` int NOT NULL,
  `note` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_rl_source` (`source_entity`,`source_id`),
  KEY `idx_rl_target` (`target_entity`,`target_id`),
  KEY `idx_rl_relation` (`relation`),
  CONSTRAINT `RelationLink_ibfk_1` FOREIGN KEY (`source_entity`) REFERENCES `entity` (`id`),
  CONSTRAINT `RelationLink_ibfk_2` FOREIGN KEY (`target_entity`) REFERENCES `entity` (`id`),
  CONSTRAINT `RelationLink_ibfk_3` FOREIGN KEY (`relation`) REFERENCES `relation` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS=1;
SET UNIQUE_CHECKS=1;
SQLEOF

echo "" >> "$OUT"
echo "-- End of schema" >> "$OUT"

echo "Done: $OUT"
wc -l "$OUT"
