# diagnostic_kb — Complete Schema Report

**Generated:** 2026-07-02
**Database:** diagnostic_kb (MySQL, localhost, root)
**Tables:** 36 total
**Mode:** READ-ONLY report. No modifications were made.

---

## Part 1: Complete CREATE TABLE Statements

### AUTHORITY TABLES (7)

```sql
CREATE TABLE `type` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(200) NOT NULL,
  `description` text,
  `sort_order` int DEFAULT '0',
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_type_name` (`name`),
  KEY `idx_type_name` (`name`)
) ENGINE=InnoDB;

CREATE TABLE `category` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(200) NOT NULL,
  `description` text,
  `parent_id` int DEFAULT NULL,
  `sort_order` int DEFAULT '0',
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_cat_name` (`name`),
  KEY `idx_cat_name` (`name`),
  KEY `idx_cat_parent` (`parent_id`),
  CONSTRAINT `category_ibfk_1` FOREIGN KEY (`parent_id`) REFERENCES `category` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE `domain` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(200) NOT NULL,
  `description` text,
  `sort_order` int DEFAULT '0',
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_dom_name` (`name`),
  KEY `idx_dom_name` (`name`)
) ENGINE=InnoDB;

CREATE TABLE `status` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(200) NOT NULL,
  `description` text,
  `sort_order` int DEFAULT '0',
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_status_name` (`name`),
  KEY `idx_status_name` (`name`)
) ENGINE=InnoDB;

CREATE TABLE `severity` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(200) NOT NULL,
  `level` int DEFAULT '0',
  `description` text,
  `sort_order` int DEFAULT '0',
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_sev_name` (`name`),
  KEY `idx_sev_name` (`name`)
) ENGINE=InnoDB;

CREATE TABLE `priority` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(200) NOT NULL,
  `level` int DEFAULT '0',
  `description` text,
  `sort_order` int DEFAULT '0',
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_pri_name` (`name`),
  KEY `idx_pri_name` (`name`)
) ENGINE=InnoDB;

CREATE TABLE `group` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(200) NOT NULL,
  `description` text,
  `parent_id` int DEFAULT NULL,
  `sort_order` int DEFAULT '0',
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_grp_name` (`name`),
  KEY `idx_grp_name` (`name`),
  KEY `idx_grp_parent` (`parent_id`),
  CONSTRAINT `group_ibfk_1` FOREIGN KEY (`parent_id`) REFERENCES `group` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB;
```

### ENTITY TABLES (12)

```sql
CREATE TABLE `incident` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `operation` varchar(200) NOT NULL,
  `source` varchar(200) DEFAULT '',
  `result` enum('ok','fail','partial') NOT NULL,
  `type_id` int DEFAULT NULL,
  `status_id` int DEFAULT NULL,
  `severity_id` int DEFAULT NULL,
  `priority_id` int DEFAULT NULL,
  `domain_id` int DEFAULT NULL,
  `category_id` int DEFAULT NULL,
  `reason` text,
  `fact_count` int DEFAULT '0',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `finalized_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_incident_operation` (`operation`),
  KEY `idx_incident_result` (`result`),
  KEY `idx_incident_created` (`created_at`),
  KEY `type_id` (`type_id`),
  KEY `status_id` (`status_id`),
  KEY `severity_id` (`severity_id`),
  KEY `priority_id` (`priority_id`),
  KEY `domain_id` (`domain_id`),
  KEY `category_id` (`category_id`),
  CONSTRAINT `incident_ibfk_1` FOREIGN KEY (`type_id`) REFERENCES `type` (`id`) ON DELETE SET NULL,
  CONSTRAINT `incident_ibfk_2` FOREIGN KEY (`status_id`) REFERENCES `status` (`id`) ON DELETE SET NULL,
  CONSTRAINT `incident_ibfk_3` FOREIGN KEY (`severity_id`) REFERENCES `severity` (`id`) ON DELETE SET NULL,
  CONSTRAINT `incident_ibfk_4` FOREIGN KEY (`priority_id`) REFERENCES `priority` (`id`) ON DELETE SET NULL,
  CONSTRAINT `incident_ibfk_5` FOREIGN KEY (`domain_id`) REFERENCES `domain` (`id`) ON DELETE SET NULL,
  CONSTRAINT `incident_ibfk_6` FOREIGN KEY (`category_id`) REFERENCES `category` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE `fact` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `incident_id` bigint NOT NULL,
  `slot` varchar(50) NOT NULL,
  `kind` varchar(50) NOT NULL,
  `type_id` int DEFAULT NULL,
  `name` varchar(200) NOT NULL,
  `value` text,
  `severity` varchar(20) DEFAULT '',
  `severity_id` int DEFAULT NULL,
  `unit` varchar(50) DEFAULT '',
  `detail` text,
  `timestamp` varchar(50) DEFAULT '',
  `source` varchar(200) DEFAULT '',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_fact_incident` (`incident_id`),
  KEY `idx_fact_slot` (`slot`),
  KEY `idx_fact_kind` (`kind`),
  KEY `type_id` (`type_id`),
  KEY `severity_id` (`severity_id`),
  CONSTRAINT `fact_ibfk_1` FOREIGN KEY (`incident_id`) REFERENCES `incident` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fact_ibfk_2` FOREIGN KEY (`type_id`) REFERENCES `type` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fact_ibfk_3` FOREIGN KEY (`severity_id`) REFERENCES `severity` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE `answer` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `incident_id` bigint NOT NULL,
  `category` varchar(50) NOT NULL,
  `question` varchar(100) NOT NULL,
  `status` enum('known','unknown','pending','n/a') NOT NULL,
  `status_id` int DEFAULT NULL,
  `type_id` int DEFAULT NULL,
  `answer` text,
  `source_type` varchar(50) DEFAULT 'report',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_answer_incident` (`incident_id`),
  KEY `idx_answer_category` (`category`),
  KEY `idx_answer_status` (`status`),
  KEY `status_id` (`status_id`),
  KEY `type_id` (`type_id`),
  CONSTRAINT `answer_ibfk_1` FOREIGN KEY (`incident_id`) REFERENCES `incident` (`id`) ON DELETE CASCADE,
  CONSTRAINT `answer_ibfk_2` FOREIGN KEY (`status_id`) REFERENCES `status` (`id`) ON DELETE SET NULL,
  CONSTRAINT `answer_ibfk_3` FOREIGN KEY (`type_id`) REFERENCES `type` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE `cause` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `incident_id` bigint NOT NULL,
  `cause_type` enum('root','contributing','runtime','behavioral') NOT NULL,
  `type_id` int DEFAULT NULL,
  `cause_text` text NOT NULL,
  `severity` int DEFAULT '0',
  `severity_id` int DEFAULT NULL,
  `evidence` text,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_cause_incident` (`incident_id`),
  KEY `idx_cause_type` (`cause_type`),
  KEY `type_id` (`type_id`),
  KEY `severity_id` (`severity_id`),
  CONSTRAINT `cause_ibfk_1` FOREIGN KEY (`incident_id`) REFERENCES `incident` (`id`) ON DELETE CASCADE,
  CONSTRAINT `cause_ibfk_2` FOREIGN KEY (`type_id`) REFERENCES `type` (`id`) ON DELETE SET NULL,
  CONSTRAINT `cause_ibfk_3` FOREIGN KEY (`severity_id`) REFERENCES `severity` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE `fix` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `incident_id` bigint NOT NULL,
  `fix_type` enum('auto','manual','recommended') NOT NULL,
  `type_id` int DEFAULT NULL,
  `fix_action` text NOT NULL,
  `result` enum('success','failed','partial','untried') DEFAULT 'untried',
  `status_id` int DEFAULT NULL,
  `priority_id` int DEFAULT NULL,
  `category_id` int DEFAULT NULL,
  `confidence` decimal(3,2) DEFAULT '0.00',
  `before_hash` varchar(64) DEFAULT '',
  `after_hash` varchar(64) DEFAULT '',
  `applied_at` timestamp NULL DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_fix_incident` (`incident_id`),
  KEY `idx_fix_result` (`result`),
  KEY `type_id` (`type_id`),
  KEY `status_id` (`status_id`),
  KEY `priority_id` (`priority_id`),
  KEY `category_id` (`category_id`),
  CONSTRAINT `fix_ibfk_1` FOREIGN KEY (`incident_id`) REFERENCES `incident` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fix_ibfk_2` FOREIGN KEY (`type_id`) REFERENCES `type` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fix_ibfk_3` FOREIGN KEY (`status_id`) REFERENCES `status` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fix_ibfk_4` FOREIGN KEY (`priority_id`) REFERENCES `priority` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fix_ibfk_5` FOREIGN KEY (`category_id`) REFERENCES `category` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE `prevention` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `incident_id` bigint NOT NULL,
  `prevention_type` enum('guard','validation','detection','process') NOT NULL,
  `type_id` int DEFAULT NULL,
  `rule_text` text NOT NULL,
  `description` text,
  `is_active` tinyint(1) DEFAULT '0',
  `status_id` int DEFAULT NULL,
  `priority_id` int DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_prev_incident` (`incident_id`),
  KEY `idx_prev_active` (`is_active`),
  KEY `type_id` (`type_id`),
  KEY `status_id` (`status_id`),
  KEY `priority_id` (`priority_id`),
  CONSTRAINT `prevention_ibfk_1` FOREIGN KEY (`incident_id`) REFERENCES `incident` (`id`) ON DELETE CASCADE,
  CONSTRAINT `prevention_ibfk_2` FOREIGN KEY (`type_id`) REFERENCES `type` (`id`) ON DELETE SET NULL,
  CONSTRAINT `prevention_ibfk_3` FOREIGN KEY (`status_id`) REFERENCES `status` (`id`) ON DELETE SET NULL,
  CONSTRAINT `prevention_ibfk_4` FOREIGN KEY (`priority_id`) REFERENCES `priority` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE `evidence` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `incident_id` bigint NOT NULL,
  `evidence_type` varchar(50) NOT NULL,
  `type_id` int DEFAULT NULL,
  `status_id` int DEFAULT NULL,
  `source_file` varchar(500) DEFAULT '',
  `source_line` int DEFAULT '0',
  `content` text NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_evidence_incident` (`incident_id`),
  KEY `idx_evidence_type` (`evidence_type`),
  KEY `type_id` (`type_id`),
  KEY `status_id` (`status_id`),
  CONSTRAINT `evidence_ibfk_1` FOREIGN KEY (`incident_id`) REFERENCES `incident` (`id`) ON DELETE CASCADE,
  CONSTRAINT `evidence_ibfk_2` FOREIGN KEY (`type_id`) REFERENCES `type` (`id`) ON DELETE SET NULL,
  CONSTRAINT `evidence_ibfk_3` FOREIGN KEY (`status_id`) REFERENCES `status` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE `problem` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `problem` varchar(500) NOT NULL,
  `description` text,
  `problem_type` varchar(100) DEFAULT '',
  `type_id` int DEFAULT NULL,
  `category` varchar(100) DEFAULT '',
  `category_id` int DEFAULT NULL,
  `domain_id` int DEFAULT NULL,
  `first_seen` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `last_seen` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `occurrence_count` int DEFAULT '1',
  `severity_id` int DEFAULT NULL,
  `status_id` int DEFAULT NULL,
  `priority_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_problem_name` (`problem`(100)),
  KEY `idx_problem_category` (`category`),
  KEY `type_id` (`type_id`),
  KEY `category_id` (`category_id`),
  KEY `domain_id` (`domain_id`),
  KEY `severity_id` (`severity_id`),
  KEY `status_id` (`status_id`),
  KEY `priority_id` (`priority_id`),
  CONSTRAINT `problem_ibfk_1` FOREIGN KEY (`type_id`) REFERENCES `type` (`id`) ON DELETE SET NULL,
  CONSTRAINT `problem_ibfk_2` FOREIGN KEY (`category_id`) REFERENCES `category` (`id`) ON DELETE SET NULL,
  CONSTRAINT `problem_ibfk_3` FOREIGN KEY (`domain_id`) REFERENCES `domain` (`id`) ON DELETE SET NULL,
  CONSTRAINT `problem_ibfk_4` FOREIGN KEY (`severity_id`) REFERENCES `severity` (`id`) ON DELETE SET NULL,
  CONSTRAINT `problem_ibfk_5` FOREIGN KEY (`status_id`) REFERENCES `status` (`id`) ON DELETE SET NULL,
  CONSTRAINT `problem_ibfk_6` FOREIGN KEY (`priority_id`) REFERENCES `priority` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE `rule` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `pattern` text NOT NULL,
  `trigger_condition` text,
  `fix_action` text NOT NULL,
  `language` varchar(20) DEFAULT '',
  `category` varchar(50) DEFAULT '',
  `type_id` int DEFAULT NULL,
  `category_id` int DEFAULT NULL,
  `domain_id` int DEFAULT NULL,
  `severity_id` int DEFAULT NULL,
  `status_id` int DEFAULT NULL,
  `priority_id` int DEFAULT NULL,
  `severity` int DEFAULT '0',
  `confidence` decimal(5,2) DEFAULT '0.00',
  `success_count` int DEFAULT '0',
  `failure_count` int DEFAULT '0',
  `source` varchar(100) DEFAULT '',
  `source_origin` varchar(100) DEFAULT '',
  `discovered_by` varchar(100) DEFAULT '',
  `verified` tinyint(1) DEFAULT '0',
  `problem_id` bigint DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `last_used` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `problem_id` (`problem_id`),
  KEY `idx_rule_pattern` (`pattern`(100)),
  KEY `idx_rule_category` (`category`),
  KEY `idx_rule_confidence` (`confidence`),
  KEY `type_id` (`type_id`),
  KEY `category_id` (`category_id`),
  KEY `domain_id` (`domain_id`),
  KEY `severity_id` (`severity_id`),
  KEY `status_id` (`status_id`),
  KEY `priority_id` (`priority_id`),
  CONSTRAINT `rule_ibfk_1` FOREIGN KEY (`problem_id`) REFERENCES `problem` (`id`) ON DELETE SET NULL,
  CONSTRAINT `rule_ibfk_2` FOREIGN KEY (`type_id`) REFERENCES `type` (`id`) ON DELETE SET NULL,
  CONSTRAINT `rule_ibfk_3` FOREIGN KEY (`category_id`) REFERENCES `category` (`id`) ON DELETE SET NULL,
  CONSTRAINT `rule_ibfk_4` FOREIGN KEY (`domain_id`) REFERENCES `domain` (`id`) ON DELETE SET NULL,
  CONSTRAINT `rule_ibfk_5` FOREIGN KEY (`severity_id`) REFERENCES `severity` (`id`) ON DELETE SET NULL,
  CONSTRAINT `rule_ibfk_6` FOREIGN KEY (`status_id`) REFERENCES `status` (`id`) ON DELETE SET NULL,
  CONSTRAINT `rule_ibfk_7` FOREIGN KEY (`priority_id`) REFERENCES `priority` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE `error` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(200) NOT NULL,
  `signature` varchar(200) DEFAULT '',
  `description` text,
  `cause` text,
  `solution` text,
  `type_id` int DEFAULT NULL,
  `category_id` int DEFAULT NULL,
  `domain_id` int DEFAULT NULL,
  `status_id` int DEFAULT NULL,
  `severity_id` int DEFAULT NULL,
  `priority_id` int DEFAULT NULL,
  `group_id` int DEFAULT NULL,
  `frequency` int DEFAULT '1',
  `confidence` decimal(3,2) DEFAULT '0.00',
  `source_db` varchar(100) DEFAULT '',
  `source_table` varchar(100) DEFAULT '',
  `source_id` bigint DEFAULT '0',
  `first_seen` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `last_seen` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_error_name` (`name`),
  KEY `idx_error_type` (`type_id`),
  KEY `idx_error_category` (`category_id`),
  KEY `idx_error_domain` (`domain_id`),
  KEY `idx_error_status` (`status_id`),
  KEY `idx_error_severity` (`severity_id`),
  KEY `idx_error_priority` (`priority_id`),
  KEY `idx_error_group` (`group_id`),
  CONSTRAINT `error_ibfk_1` FOREIGN KEY (`type_id`) REFERENCES `type` (`id`) ON DELETE SET NULL,
  CONSTRAINT `error_ibfk_2` FOREIGN KEY (`category_id`) REFERENCES `category` (`id`) ON DELETE SET NULL,
  CONSTRAINT `error_ibfk_3` FOREIGN KEY (`domain_id`) REFERENCES `domain` (`id`) ON DELETE SET NULL,
  CONSTRAINT `error_ibfk_4` FOREIGN KEY (`status_id`) REFERENCES `status` (`id`) ON DELETE SET NULL,
  CONSTRAINT `error_ibfk_5` FOREIGN KEY (`severity_id`) REFERENCES `severity` (`id`) ON DELETE SET NULL,
  CONSTRAINT `error_ibfk_6` FOREIGN KEY (`priority_id`) REFERENCES `priority` (`id`) ON DELETE SET NULL,
  CONSTRAINT `error_ibfk_7` FOREIGN KEY (`group_id`) REFERENCES `group` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE `question` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `question_text` text NOT NULL,
  `fingerprint` varchar(32) NOT NULL,
  `type_id` int DEFAULT NULL,
  `category_id` int DEFAULT NULL,
  `domain_id` int DEFAULT NULL,
  `group_id` int DEFAULT NULL,
  `category` varchar(100) DEFAULT '',
  `domain` varchar(100) DEFAULT '',
  `is_answered` tinyint(1) DEFAULT '0',
  `is_active` tinyint(1) DEFAULT '1',
  `occurrence_count` int DEFAULT '1',
  `source_db` varchar(100) DEFAULT '',
  `source_table` varchar(100) DEFAULT '',
  `source_id` bigint DEFAULT '0',
  `source_column` varchar(100) DEFAULT '',
  `migrated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `fingerprint` (`fingerprint`),
  KEY `idx_question_fp` (`fingerprint`),
  KEY `idx_question_type` (`type_id`),
  KEY `idx_question_category` (`category`),
  KEY `idx_question_domain` (`domain`),
  KEY `idx_question_answered` (`is_answered`),
  KEY `idx_question_source` (`source_db`,`source_table`),
  KEY `category_id` (`category_id`),
  KEY `domain_id` (`domain_id`),
  KEY `group_id` (`group_id`),
  CONSTRAINT `question_ibfk_1` FOREIGN KEY (`type_id`) REFERENCES `question_type` (`id`) ON DELETE SET NULL,
  CONSTRAINT `question_ibfk_2` FOREIGN KEY (`category_id`) REFERENCES `category` (`id`) ON DELETE SET NULL,
  CONSTRAINT `question_ibfk_3` FOREIGN KEY (`domain_id`) REFERENCES `domain` (`id`) ON DELETE SET NULL,
  CONSTRAINT `question_ibfk_4` FOREIGN KEY (`group_id`) REFERENCES `group` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE `report` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `title` varchar(200) DEFAULT '',
  `incident_id` bigint DEFAULT NULL,
  `type_id` int DEFAULT NULL,
  `category_id` int DEFAULT NULL,
  `domain_id` int DEFAULT NULL,
  `status_id` int DEFAULT NULL,
  `severity_id` int DEFAULT NULL,
  `priority_id` int DEFAULT NULL,
  `group_id` int DEFAULT NULL,
  `rendered_text` text,
  `rendered_at` timestamp NULL DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `type_id` (`type_id`),
  KEY `category_id` (`category_id`),
  KEY `domain_id` (`domain_id`),
  KEY `severity_id` (`severity_id`),
  KEY `priority_id` (`priority_id`),
  KEY `group_id` (`group_id`),
  KEY `idx_report_incident` (`incident_id`),
  KEY `idx_report_status` (`status_id`),
  CONSTRAINT `report_ibfk_1` FOREIGN KEY (`incident_id`) REFERENCES `incident` (`id`) ON DELETE SET NULL,
  CONSTRAINT `report_ibfk_6` FOREIGN KEY (`type_id`) REFERENCES `type` (`id`) ON DELETE SET NULL,
  CONSTRAINT `report_ibfk_7` FOREIGN KEY (`category_id`) REFERENCES `category` (`id`) ON DELETE SET NULL,
  CONSTRAINT `report_ibfk_8` FOREIGN KEY (`domain_id`) REFERENCES `domain` (`id`) ON DELETE SET NULL,
  CONSTRAINT `report_ibfk_9` FOREIGN KEY (`status_id`) REFERENCES `status` (`id`) ON DELETE SET NULL,
  CONSTRAINT `report_ibfk_10` FOREIGN KEY (`severity_id`) REFERENCES `severity` (`id`) ON DELETE SET NULL,
  CONSTRAINT `report_ibfk_11` FOREIGN KEY (`priority_id`) REFERENCES `priority` (`id`) ON DELETE SET NULL,
  CONSTRAINT `report_ibfk_12` FOREIGN KEY (`group_id`) REFERENCES `group` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB;
```

### GOVERNANCE TABLES (4)

```sql
CREATE TABLE `law` (
  `id` int NOT NULL AUTO_INCREMENT,
  `law_code` varchar(20) NOT NULL,
  `law_name` varchar(200) NOT NULL,
  `law_text` text NOT NULL,
  `domain_id` int DEFAULT NULL,
  `category_id` int DEFAULT NULL,
  `status_id` int DEFAULT '42',
  `priority_id` int DEFAULT '12',
  `source` varchar(200) DEFAULT 'conversation',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `law_code` (`law_code`),
  KEY `status_id` (`status_id`),
  KEY `priority_id` (`priority_id`),
  KEY `idx_law_code` (`law_code`),
  KEY `idx_law_domain` (`domain_id`),
  KEY `idx_law_category` (`category_id`),
  CONSTRAINT `law_ibfk_1` FOREIGN KEY (`domain_id`) REFERENCES `domain` (`id`),
  CONSTRAINT `law_ibfk_2` FOREIGN KEY (`category_id`) REFERENCES `category` (`id`),
  CONSTRAINT `law_ibfk_3` FOREIGN KEY (`status_id`) REFERENCES `status` (`id`),
  CONSTRAINT `law_ibfk_4` FOREIGN KEY (`priority_id`) REFERENCES `priority` (`id`)
) ENGINE=InnoDB;

CREATE TABLE `pattern` (
  `id` int NOT NULL AUTO_INCREMENT,
  `pattern_code` varchar(20) NOT NULL,
  `pattern_name` varchar(200) NOT NULL,
  `pattern_text` text NOT NULL,
  `domain_id` int DEFAULT NULL,
  `category_id` int DEFAULT NULL,
  `status_id` int DEFAULT '42',
  `source` varchar(200) DEFAULT 'vbpack',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `pattern_code` (`pattern_code`),
  KEY `status_id` (`status_id`),
  KEY `idx_pattern_code` (`pattern_code`),
  KEY `idx_pattern_category` (`category_id`),
  KEY `idx_pattern_domain` (`domain_id`),
  CONSTRAINT `pattern_ibfk_1` FOREIGN KEY (`domain_id`) REFERENCES `domain` (`id`),
  CONSTRAINT `pattern_ibfk_2` FOREIGN KEY (`category_id`) REFERENCES `category` (`id`),
  CONSTRAINT `pattern_ibfk_3` FOREIGN KEY (`status_id`) REFERENCES `status` (`id`)
) ENGINE=InnoDB;

CREATE TABLE `pattern_law` (
  `pattern_id` int NOT NULL,
  `law_id` int NOT NULL,
  `relationship` varchar(20) NOT NULL DEFAULT 'violates',
  `note` varchar(200) DEFAULT '',
  PRIMARY KEY (`pattern_id`,`law_id`,`relationship`),
  KEY `idx_plaw_law` (`law_id`),
  KEY `idx_plaw_rel` (`relationship`),
  CONSTRAINT `pattern_law_ibfk_1` FOREIGN KEY (`pattern_id`) REFERENCES `pattern` (`id`) ON DELETE CASCADE,
  CONSTRAINT `pattern_law_ibfk_2` FOREIGN KEY (`law_id`) REFERENCES `law` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE `decision` (
  `id` int NOT NULL AUTO_INCREMENT,
  `decision_code` varchar(50) NOT NULL,
  `decision_name` varchar(200) NOT NULL,
  `context` text NOT NULL,
  `choice` text NOT NULL,
  `rationale` text NOT NULL,
  `domain_id` int DEFAULT NULL,
  `status_id` int DEFAULT '42',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `decision_code` (`decision_code`),
  KEY `status_id` (`status_id`),
  KEY `idx_decision_code` (`decision_code`),
  KEY `idx_decision_domain` (`domain_id`),
  CONSTRAINT `decision_ibfk_1` FOREIGN KEY (`domain_id`) REFERENCES `domain` (`id`),
  CONSTRAINT `decision_ibfk_2` FOREIGN KEY (`status_id`) REFERENCES `status` (`id`)
) ENGINE=InnoDB;
```

### JOIN TABLES (10 report_* + 2 legacy)

```sql
CREATE TABLE `report_error` (
  `report_id` bigint NOT NULL,
  `error_id` bigint NOT NULL,
  `sort_order` int DEFAULT '0',
  PRIMARY KEY (`report_id`,`error_id`),
  KEY `idx_re_error` (`error_id`),
  CONSTRAINT `report_error_ibfk_1` FOREIGN KEY (`report_id`) REFERENCES `report` (`id`) ON DELETE CASCADE,
  CONSTRAINT `report_error_ibfk_2` FOREIGN KEY (`error_id`) REFERENCES `error` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE `report_problem` (
  `report_id` bigint NOT NULL,
  `problem_id` bigint NOT NULL,
  PRIMARY KEY (`report_id`,`problem_id`),
  KEY `idx_rp_problem` (`problem_id`),
  CONSTRAINT `report_problem_ibfk_1` FOREIGN KEY (`report_id`) REFERENCES `report` (`id`) ON DELETE CASCADE,
  CONSTRAINT `report_problem_ibfk_2` FOREIGN KEY (`problem_id`) REFERENCES `problem` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE `report_cause` (
  `report_id` bigint NOT NULL,
  `cause_id` bigint NOT NULL,
  PRIMARY KEY (`report_id`,`cause_id`),
  KEY `idx_rc_cause` (`cause_id`),
  CONSTRAINT `report_cause_ibfk_1` FOREIGN KEY (`report_id`) REFERENCES `report` (`id`) ON DELETE CASCADE,
  CONSTRAINT `report_cause_ibfk_2` FOREIGN KEY (`cause_id`) REFERENCES `cause` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE `report_fix` (
  `report_id` bigint NOT NULL,
  `fix_id` bigint NOT NULL,
  `sort_order` int DEFAULT '0',
  PRIMARY KEY (`report_id`,`fix_id`),
  KEY `idx_rf_fix` (`fix_id`),
  CONSTRAINT `report_fix_ibfk_1` FOREIGN KEY (`report_id`) REFERENCES `report` (`id`) ON DELETE CASCADE,
  CONSTRAINT `report_fix_ibfk_2` FOREIGN KEY (`fix_id`) REFERENCES `fix` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE `report_prevention` (
  `report_id` bigint NOT NULL,
  `prevention_id` bigint NOT NULL,
  PRIMARY KEY (`report_id`,`prevention_id`),
  KEY `idx_rprev_prevention` (`prevention_id`),
  CONSTRAINT `report_prevention_ibfk_1` FOREIGN KEY (`report_id`) REFERENCES `report` (`id`) ON DELETE CASCADE,
  CONSTRAINT `report_prevention_ibfk_2` FOREIGN KEY (`prevention_id`) REFERENCES `prevention` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE `report_fact` (
  `report_id` bigint NOT NULL,
  `fact_id` bigint NOT NULL,
  `sort_order` int DEFAULT '0',
  PRIMARY KEY (`report_id`,`fact_id`),
  KEY `idx_rf_fact` (`fact_id`),
  CONSTRAINT `report_fact_ibfk_1` FOREIGN KEY (`report_id`) REFERENCES `report` (`id`) ON DELETE CASCADE,
  CONSTRAINT `report_fact_ibfk_2` FOREIGN KEY (`fact_id`) REFERENCES `fact` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE `report_answer` (
  `report_id` bigint NOT NULL,
  `answer_id` bigint NOT NULL,
  PRIMARY KEY (`report_id`,`answer_id`),
  KEY `idx_ra_answer` (`answer_id`),
  CONSTRAINT `report_answer_ibfk_1` FOREIGN KEY (`report_id`) REFERENCES `report` (`id`) ON DELETE CASCADE,
  CONSTRAINT `report_answer_ibfk_2` FOREIGN KEY (`answer_id`) REFERENCES `answer` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE `report_evidence` (
  `report_id` bigint NOT NULL,
  `evidence_id` bigint NOT NULL,
  PRIMARY KEY (`report_id`,`evidence_id`),
  KEY `idx_re_evidence` (`evidence_id`),
  CONSTRAINT `report_evidence_ibfk_1` FOREIGN KEY (`report_id`) REFERENCES `report` (`id`) ON DELETE CASCADE,
  CONSTRAINT `report_evidence_ibfk_2` FOREIGN KEY (`evidence_id`) REFERENCES `evidence` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE `report_rule` (
  `report_id` bigint NOT NULL,
  `rule_id` bigint NOT NULL,
  PRIMARY KEY (`report_id`,`rule_id`),
  KEY `idx_rr_rule` (`rule_id`),
  CONSTRAINT `report_rule_ibfk_1` FOREIGN KEY (`report_id`) REFERENCES `report` (`id`) ON DELETE CASCADE,
  CONSTRAINT `report_rule_ibfk_2` FOREIGN KEY (`rule_id`) REFERENCES `rule` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE `report_question` (
  `report_id` bigint NOT NULL,
  `question_id` bigint NOT NULL,
  PRIMARY KEY (`report_id`,`question_id`),
  KEY `idx_rq_question` (`question_id`),
  CONSTRAINT `report_question_ibfk_1` FOREIGN KEY (`report_id`) REFERENCES `report` (`id`) ON DELETE CASCADE,
  CONSTRAINT `report_question_ibfk_2` FOREIGN KEY (`question_id`) REFERENCES `question` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE `incident_problem` (
  `incident_id` bigint NOT NULL,
  `problem_id` bigint NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`incident_id`,`problem_id`),
  KEY `idx_iproblem_problem` (`problem_id`),
  CONSTRAINT `incident_problem_ibfk_1` FOREIGN KEY (`incident_id`) REFERENCES `incident` (`id`) ON DELETE CASCADE,
  CONSTRAINT `incident_problem_ibfk_2` FOREIGN KEY (`problem_id`) REFERENCES `problem` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE `problem_solution` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `problem_id` bigint NOT NULL,
  `solution` text NOT NULL,
  `weight` decimal(3,2) DEFAULT '0.50',
  `auto_apply` tinyint(1) DEFAULT '0',
  `scope` varchar(100) DEFAULT '',
  `fault_code` varchar(100) DEFAULT '',
  `success_count` int DEFAULT '0',
  `failure_count` int DEFAULT '0',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_psol_problem` (`problem_id`),
  KEY `idx_psol_auto` (`auto_apply`),
  CONSTRAINT `problem_solution_ibfk_1` FOREIGN KEY (`problem_id`) REFERENCES `problem` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB;
```

### LEGACY / DEPRECATED TABLES (3)

```sql
CREATE TABLE `question_type` (
  `id` int NOT NULL AUTO_INCREMENT,
  `type_name` varchar(100) NOT NULL,
  `description` text,
  `sort_order` int DEFAULT '0',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `type_name` (`type_name`)
) ENGINE=InnoDB;

CREATE TABLE `foundation_law` (
  `id` int NOT NULL AUTO_INCREMENT,
  `law_code` varchar(20) NOT NULL,
  `law_name` varchar(200) NOT NULL,
  `law_text` text NOT NULL,
  `domain` varchar(50) NOT NULL DEFAULT 'architecture',
  `scope` varchar(50) NOT NULL DEFAULT 'universal',
  `severity` varchar(20) NOT NULL DEFAULT 'mandatory',
  `source` varchar(200) DEFAULT 'conversation',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `law_code` (`law_code`),
  KEY `idx_foundation_law_code` (`law_code`),
  KEY `idx_foundation_law_domain` (`domain`),
  KEY `idx_foundation_law_scope` (`scope`)
) ENGINE=InnoDB;
```

---

## Part 2: ER Summary

### Table Classification

| Category | Tables | Count |
|---|---|---|
| **Authority** | type, category, domain, status, severity, priority, group | 7 |
| **Entity** | incident, fact, answer, cause, fix, prevention, evidence, problem, rule, error, question, report | 12 |
| **Governance** | law, pattern, pattern_law, decision | 4 |
| **Join (report_*)** | report_error, report_problem, report_cause, report_fix, report_prevention, report_fact, report_answer, report_evidence, report_rule, report_question | 10 |
| **Join (legacy)** | incident_problem, problem_solution | 2 |
| **Legacy/Deprecated** | question_type, foundation_law | 2 |
| **Total** | | **37** |

### Which Tables Reference Each Authority

| Authority | Referenced By |
|---|---|
| **type** | answer, cause, error, evidence, fact, fix, incident, prevention, problem, report, rule (11 tables) |
| **category** | category (self), error, fix, incident, law, pattern, problem, question, report, rule (10 tables) |
| **domain** | decision, error, incident, law, pattern, problem, question, report, rule (9 tables) |
| **status** | answer, decision, error, evidence, fix, incident, law, pattern, prevention, problem, report, rule (12 tables) |
| **severity** | cause, error, fact, incident, problem, report, rule (7 tables) |
| **priority** | error, fix, incident, law, prevention, problem, report, rule (8 tables) |
| **group** | group (self), error, question, report (3 tables) |

### Entity Relationship Map

```
incident (anchor)
  ├── fact          (incident_id FK, CASCADE)
  ├── answer        (incident_id FK, CASCADE)
  ├── cause         (incident_id FK, CASCADE)
  ├── fix           (incident_id FK, CASCADE)
  ├── prevention    (incident_id FK, CASCADE)
  ├── evidence      (incident_id FK, CASCADE)
  └── incident_problem → problem (M:N)

problem
  ├── problem_solution   (problem_id FK, CASCADE)
  └── rule               (problem_id FK, SET NULL)

report (container of relationships)
  ├── report_error       → error     (M:N)
  ├── report_problem     → problem   (M:N)
  ├── report_cause       → cause     (M:N)
  ├── report_fix         → fix       (M:N)
  ├── report_prevention  → prevention(M:N)
  ├── report_fact        → fact      (M:N)
  ├── report_answer      → answer    (M:N)
  ├── report_evidence    → evidence  (M:N)
  ├── report_rule        → rule      (M:N)
  └── report_question    → question  (M:N)

law
  └── pattern_law → pattern (M:N)

pattern
  └── pattern_law → law (M:N)

decision (standalone — references domain, status)
```

---

## Part 3: Completeness Analysis

### Mandatory (NOT NULL) Fields Per Entity

| Entity | NOT NULL Fields | Nullable Authority FKs |
|---|---|---|
| **incident** | id, operation, result | type_id, status_id, severity_id, priority_id, domain_id, category_id |
| **fact** | id, incident_id, slot, kind, name | type_id, severity_id |
| **answer** | id, incident_id, category, question, status | status_id, type_id |
| **cause** | id, incident_id, cause_type, cause_text | type_id, severity_id |
| **fix** | id, incident_id, fix_type, fix_action | type_id, status_id, priority_id, category_id |
| **prevention** | id, incident_id, prevention_type, rule_text | type_id, status_id, priority_id |
| **evidence** | id, incident_id, evidence_type, content | type_id, status_id |
| **problem** | id, problem | type_id, category_id, domain_id, severity_id, status_id, priority_id |
| **rule** | id, pattern, fix_action | type_id, category_id, domain_id, severity_id, status_id, priority_id |
| **error** | id, name | type_id, category_id, domain_id, status_id, severity_id, priority_id, group_id |
| **question** | id, question_text, fingerprint | type_id, category_id, domain_id, group_id |
| **report** | id | incident_id, type_id, category_id, domain_id, status_id, severity_id, priority_id, group_id |

### The Problem: ZERO Completeness Enforcement

**Every single authority FK is nullable.** Not one entity enforces completeness. Any row can exist with all authority FKs set to NULL. This means:

- An error can exist without a type, category, domain, status, severity, priority, or group.
- A report can exist without an incident, type, category, domain, status, severity, priority, or group.
- A question can exist without a type, category, domain, or group.

**The database does NOT enforce the architecture.** It allows incomplete records by design.

---

## Part 4: Architectural Violations Found

### A. ENUM Columns (6 remaining — violates ENU pattern)

| Table | Column | ENUM Type | Should Be |
|---|---|---|---|
| incident | result | enum('ok','fail','partial') | status_id FK |
| answer | status | enum('known','unknown','pending','n/a') | status_id FK |
| cause | cause_type | enum('root','contributing','runtime','behavioral') | type_id FK |
| fix | fix_type | enum('auto','manual','recommended') | type_id FK |
| fix | result | enum('success','failed','partial','untried') | status_id FK |
| prevention | prevention_type | enum('guard','validation','detection','process') | type_id FK |

### B. Duplicated Concepts (10 tables — text column + FK to same authority)

| Table | Text Column | FK Column | Violates |
|---|---|---|---|
| answer | category | category_id (missing) | LAW1 — meaning stored twice |
| answer | status (ENUM) | status_id | LAW1 — meaning stored twice |
| cause | cause_type (ENUM) | type_id | LAW1 — meaning stored twice |
| cause | severity (int) | severity_id | LAW1 — meaning stored twice |
| evidence | evidence_type | type_id | LAW1 — meaning stored twice |
| fact | severity (varchar) | severity_id | LAW1 — meaning stored twice |
| fix | fix_type (ENUM) | type_id | LAW1 — meaning stored twice |
| fix | result (ENUM) | status_id | LAW1 — meaning stored twice |
| incident | result (ENUM) | status_id | LAW1 — meaning stored twice |
| prevention | prevention_type (ENUM) | type_id | LAW1 — meaning stored twice |
| problem | problem_type | type_id | LAW1 — meaning stored twice |
| problem | category | category_id | LAW1 — meaning stored twice |
| question | category | category_id | LAW1 — meaning stored twice |
| question | domain | domain_id | LAW1 — meaning stored twice |
| rule | category | category_id | LAW1 — meaning stored twice |
| rule | severity (int) | severity_id | LAW1 — meaning stored twice |

### C. Wrong FK Target (1 table)

| Table | Column | References | Should Reference |
|---|---|---|---|
| question | type_id | question_type (legacy) | type (authority) |

### D. Deprecated Tables (2 tables)

| Table | Status | Replaced By |
|---|---|---|
| foundation_law | deprecated | law + pattern + pattern_law + decision |
| question_type | legacy | type (authority) |

### E. Missing Authority FKs (gaps)

| Entity | Has | Missing |
|---|---|---|
| answer | status_id, type_id | category_id, domain_id |
| cause | type_id, severity_id | category_id, status_id, priority_id |
| evidence | type_id, status_id | category_id, domain_id, severity_id, priority_id |
| fact | type_id, severity_id | category_id, domain_id, status_id, priority_id |
| fix | type_id, status_id, priority_id, category_id | domain_id, severity_id, group_id |
| prevention | type_id, status_id, priority_id | category_id, domain_id, severity_id |
| problem | type_id, category_id, domain_id, severity_id, status_id, priority_id | group_id |
| question | type_id, category_id, domain_id, group_id | status_id, severity_id, priority_id |
| rule | type_id, category_id, domain_id, severity_id, status_id, priority_id | group_id |
| error | type_id, category_id, domain_id, status_id, severity_id, priority_id, group_id | (complete) |
| incident | type_id, status_id, severity_id, priority_id, domain_id, category_id | group_id |
| report | type_id, category_id, domain_id, status_id, severity_id, priority_id, group_id | (complete) |

### F. No CHECK Constraints

The database has **zero CHECK constraints**. No validation is performed at the database level beyond NOT NULL and FK existence.

---

## Part 5: Summary of Issues

| Issue | Count | Severity |
|---|---|---|
| ENUM columns (violates ENU) | 6 | High — violates LAW1 |
| Duplicated concepts (text + FK) | 16 | High — violates LAW1 |
| Wrong FK target (question→question_type) | 1 | Medium — legacy |
| Deprecated tables | 2 | Low — cleanup |
| Nullable authority FKs (no completeness) | 60 | Critical — no enforcement |
| Missing authority FKs (gaps) | 25 | Medium — incomplete schema |
| CHECK constraints | 0 | Medium — no validation |

### The Core Finding

The database **models** the architecture but does not **enforce** it. Every authority FK is nullable. Every ENUM still exists alongside its FK replacement. Duplicated text columns remain. The schema is half-migrated — it has the FKs but hasn't removed the old text/ENUM columns, and it hasn't made the FKs mandatory.

The next step is to decide: which entities need completeness contracts, and which authority FKs should become NOT NULL.
