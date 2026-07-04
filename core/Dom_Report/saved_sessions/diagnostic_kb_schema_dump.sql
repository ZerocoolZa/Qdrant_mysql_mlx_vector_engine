
/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
DROP TABLE IF EXISTS `answer`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `answer` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `incident_id` bigint NOT NULL,
  `category` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `question` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` enum('known','unknown','pending','n/a') COLLATE utf8mb4_unicode_ci NOT NULL,
  `status_id` int DEFAULT NULL,
  `type_id` int DEFAULT NULL,
  `answer` text COLLATE utf8mb4_unicode_ci,
  `source_type` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT 'report',
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
) ENGINE=InnoDB AUTO_INCREMENT=35 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `category`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `category` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `parent_id` int DEFAULT NULL,
  `sort_order` int DEFAULT '0',
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_cat_name` (`name`),
  KEY `idx_cat_name` (`name`),
  KEY `idx_cat_parent` (`parent_id`),
  CONSTRAINT `category_ibfk_1` FOREIGN KEY (`parent_id`) REFERENCES `category` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=35032 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `cause`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `cause` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `incident_id` bigint NOT NULL,
  `cause_type` enum('root','contributing','runtime','behavioral') COLLATE utf8mb4_unicode_ci NOT NULL,
  `type_id` int DEFAULT NULL,
  `cause_text` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `severity` int DEFAULT '0',
  `severity_id` int DEFAULT NULL,
  `evidence` text COLLATE utf8mb4_unicode_ci,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_cause_incident` (`incident_id`),
  KEY `idx_cause_type` (`cause_type`),
  KEY `type_id` (`type_id`),
  KEY `severity_id` (`severity_id`),
  CONSTRAINT `cause_ibfk_1` FOREIGN KEY (`incident_id`) REFERENCES `incident` (`id`) ON DELETE CASCADE,
  CONSTRAINT `cause_ibfk_2` FOREIGN KEY (`type_id`) REFERENCES `type` (`id`) ON DELETE SET NULL,
  CONSTRAINT `cause_ibfk_3` FOREIGN KEY (`severity_id`) REFERENCES `severity` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `Class`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `Class` (
  `Id` bigint NOT NULL AUTO_INCREMENT,
  `Name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `Code` longtext COLLATE utf8mb4_unicode_ci,
  `BCL` longtext COLLATE utf8mb4_unicode_ci,
  `BCLIR` longtext COLLATE utf8mb4_unicode_ci,
  `Graph` longtext COLLATE utf8mb4_unicode_ci,
  `Description` text COLLATE utf8mb4_unicode_ci,
  `Type` int DEFAULT NULL,
  `Category` int DEFAULT NULL,
  `Domain` int DEFAULT NULL,
  `Status` int DEFAULT NULL,
  `Priority` int DEFAULT NULL,
  `Severity` int DEFAULT NULL,
  `Group` int DEFAULT NULL,
  `CreatedAt` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`Id`),
  KEY `Category` (`Category`),
  KEY `Status` (`Status`),
  KEY `Priority` (`Priority`),
  KEY `Severity` (`Severity`),
  KEY `Group` (`Group`),
  KEY `idx_class_name` (`Name`),
  KEY `idx_class_type` (`Type`),
  KEY `idx_class_domain` (`Domain`),
  CONSTRAINT `class_ibfk_1` FOREIGN KEY (`Type`) REFERENCES `type` (`id`),
  CONSTRAINT `class_ibfk_2` FOREIGN KEY (`Category`) REFERENCES `category` (`id`),
  CONSTRAINT `class_ibfk_3` FOREIGN KEY (`Domain`) REFERENCES `domain` (`id`),
  CONSTRAINT `class_ibfk_4` FOREIGN KEY (`Status`) REFERENCES `status` (`id`),
  CONSTRAINT `class_ibfk_5` FOREIGN KEY (`Priority`) REFERENCES `priority` (`id`),
  CONSTRAINT `class_ibfk_6` FOREIGN KEY (`Severity`) REFERENCES `severity` (`id`),
  CONSTRAINT `class_ibfk_7` FOREIGN KEY (`Group`) REFERENCES `group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ClassComputationUnit`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ClassComputationUnit` (
  `Class` bigint NOT NULL,
  `ComputationUnit` bigint NOT NULL,
  `Sequence` int DEFAULT '0',
  PRIMARY KEY (`Class`,`ComputationUnit`),
  KEY `idx_ccu_unit` (`ComputationUnit`),
  KEY `idx_ccu_sequence` (`Sequence`),
  CONSTRAINT `classcomputationunit_ibfk_1` FOREIGN KEY (`Class`) REFERENCES `Class` (`Id`) ON DELETE CASCADE,
  CONSTRAINT `classcomputationunit_ibfk_2` FOREIGN KEY (`ComputationUnit`) REFERENCES `ComputationUnit` (`Id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ComputationUnit`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ComputationUnit` (
  `Id` bigint NOT NULL AUTO_INCREMENT,
  `Name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `Code` longtext COLLATE utf8mb4_unicode_ci,
  `BCL` longtext COLLATE utf8mb4_unicode_ci,
  `BCLIR` longtext COLLATE utf8mb4_unicode_ci,
  `Graph` longtext COLLATE utf8mb4_unicode_ci,
  `Description` text COLLATE utf8mb4_unicode_ci,
  `Type` int DEFAULT NULL,
  `Category` int DEFAULT NULL,
  `Domain` int DEFAULT NULL,
  `Status` int DEFAULT NULL,
  `Priority` int DEFAULT NULL,
  `Severity` int DEFAULT NULL,
  `Group` int DEFAULT NULL,
  `CreatedAt` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`Id`),
  KEY `Category` (`Category`),
  KEY `Status` (`Status`),
  KEY `Priority` (`Priority`),
  KEY `Severity` (`Severity`),
  KEY `Group` (`Group`),
  KEY `idx_cu_name` (`Name`),
  KEY `idx_cu_type` (`Type`),
  KEY `idx_cu_domain` (`Domain`),
  CONSTRAINT `computationunit_ibfk_1` FOREIGN KEY (`Type`) REFERENCES `type` (`id`),
  CONSTRAINT `computationunit_ibfk_2` FOREIGN KEY (`Category`) REFERENCES `category` (`id`),
  CONSTRAINT `computationunit_ibfk_3` FOREIGN KEY (`Domain`) REFERENCES `domain` (`id`),
  CONSTRAINT `computationunit_ibfk_4` FOREIGN KEY (`Status`) REFERENCES `status` (`id`),
  CONSTRAINT `computationunit_ibfk_5` FOREIGN KEY (`Priority`) REFERENCES `priority` (`id`),
  CONSTRAINT `computationunit_ibfk_6` FOREIGN KEY (`Severity`) REFERENCES `severity` (`id`),
  CONSTRAINT `computationunit_ibfk_7` FOREIGN KEY (`Group`) REFERENCES `group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `ComputationUnitMethod`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ComputationUnitMethod` (
  `ComputationUnit` bigint NOT NULL,
  `Method` bigint NOT NULL,
  `Sequence` int DEFAULT '0',
  `Role` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT '',
  PRIMARY KEY (`ComputationUnit`,`Method`),
  KEY `idx_cum_method` (`Method`),
  KEY `idx_cum_sequence` (`Sequence`),
  CONSTRAINT `computationunitmethod_ibfk_1` FOREIGN KEY (`ComputationUnit`) REFERENCES `ComputationUnit` (`Id`) ON DELETE CASCADE,
  CONSTRAINT `computationunitmethod_ibfk_2` FOREIGN KEY (`Method`) REFERENCES `Method` (`Id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `decision`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `decision` (
  `id` int NOT NULL AUTO_INCREMENT,
  `decision_code` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `decision_name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `context` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `choice` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `rationale` text COLLATE utf8mb4_unicode_ci NOT NULL,
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
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `domain`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `domain` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `sort_order` int DEFAULT '0',
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_dom_name` (`name`),
  KEY `idx_dom_name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=281 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `error`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `error` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `signature` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `description` text COLLATE utf8mb4_unicode_ci,
  `cause` text COLLATE utf8mb4_unicode_ci,
  `solution` text COLLATE utf8mb4_unicode_ci,
  `type_id` int DEFAULT NULL,
  `category_id` int DEFAULT NULL,
  `domain_id` int DEFAULT NULL,
  `status_id` int DEFAULT NULL,
  `severity_id` int DEFAULT NULL,
  `priority_id` int DEFAULT NULL,
  `group_id` int DEFAULT NULL,
  `frequency` int DEFAULT '1',
  `confidence` decimal(3,2) DEFAULT '0.00',
  `source_db` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `source_table` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT '',
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
) ENGINE=InnoDB AUTO_INCREMENT=369 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `evidence`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `evidence` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `incident_id` bigint NOT NULL,
  `evidence_type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `type_id` int DEFAULT NULL,
  `status_id` int DEFAULT NULL,
  `source_file` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `source_line` int DEFAULT '0',
  `content` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_evidence_incident` (`incident_id`),
  KEY `idx_evidence_type` (`evidence_type`),
  KEY `type_id` (`type_id`),
  KEY `status_id` (`status_id`),
  CONSTRAINT `evidence_ibfk_1` FOREIGN KEY (`incident_id`) REFERENCES `incident` (`id`) ON DELETE CASCADE,
  CONSTRAINT `evidence_ibfk_2` FOREIGN KEY (`type_id`) REFERENCES `type` (`id`) ON DELETE SET NULL,
  CONSTRAINT `evidence_ibfk_3` FOREIGN KEY (`status_id`) REFERENCES `status` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `fact`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `fact` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `incident_id` bigint NOT NULL,
  `slot` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `kind` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `type_id` int DEFAULT NULL,
  `name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `value` text COLLATE utf8mb4_unicode_ci,
  `severity` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `severity_id` int DEFAULT NULL,
  `unit` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `detail` text COLLATE utf8mb4_unicode_ci,
  `timestamp` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `source` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT '',
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
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `fix`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `fix` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `incident_id` bigint NOT NULL,
  `fix_type` enum('auto','manual','recommended') COLLATE utf8mb4_unicode_ci NOT NULL,
  `type_id` int DEFAULT NULL,
  `fix_action` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `result` enum('success','failed','partial','untried') COLLATE utf8mb4_unicode_ci DEFAULT 'untried',
  `status_id` int DEFAULT NULL,
  `priority_id` int DEFAULT NULL,
  `category_id` int DEFAULT NULL,
  `confidence` decimal(3,2) DEFAULT '0.00',
  `before_hash` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `after_hash` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT '',
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
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `foundation_law`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `foundation_law` (
  `id` int NOT NULL AUTO_INCREMENT,
  `law_code` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `law_name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `law_text` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `domain` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'architecture',
  `scope` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'universal',
  `severity` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'mandatory',
  `source` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT 'conversation',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `law_code` (`law_code`),
  KEY `idx_foundation_law_code` (`law_code`),
  KEY `idx_foundation_law_domain` (`domain`),
  KEY `idx_foundation_law_scope` (`scope`)
) ENGINE=InnoDB AUTO_INCREMENT=21 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `group`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `group` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `parent_id` int DEFAULT NULL,
  `sort_order` int DEFAULT '0',
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_grp_name` (`name`),
  KEY `idx_grp_name` (`name`),
  KEY `idx_grp_parent` (`parent_id`),
  CONSTRAINT `group_ibfk_1` FOREIGN KEY (`parent_id`) REFERENCES `group` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `incident`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `incident` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `operation` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `source` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `result` enum('ok','fail','partial') COLLATE utf8mb4_unicode_ci NOT NULL,
  `type_id` int DEFAULT NULL,
  `status_id` int DEFAULT NULL,
  `severity_id` int DEFAULT NULL,
  `priority_id` int DEFAULT NULL,
  `domain_id` int DEFAULT NULL,
  `category_id` int DEFAULT NULL,
  `reason` text COLLATE utf8mb4_unicode_ci,
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
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `incident_problem`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `incident_problem` (
  `incident_id` bigint NOT NULL,
  `problem_id` bigint NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`incident_id`,`problem_id`),
  KEY `idx_iproblem_problem` (`problem_id`),
  CONSTRAINT `incident_problem_ibfk_1` FOREIGN KEY (`incident_id`) REFERENCES `incident` (`id`) ON DELETE CASCADE,
  CONSTRAINT `incident_problem_ibfk_2` FOREIGN KEY (`problem_id`) REFERENCES `problem` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `law`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `law` (
  `id` int NOT NULL AUTO_INCREMENT,
  `law_code` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `law_name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `law_text` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `domain_id` int DEFAULT NULL,
  `category_id` int DEFAULT NULL,
  `status_id` int DEFAULT '42',
  `priority_id` int DEFAULT '12',
  `source` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT 'conversation',
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
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `Method`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `Method` (
  `Id` bigint NOT NULL AUTO_INCREMENT,
  `Name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `Signature` text COLLATE utf8mb4_unicode_ci,
  `Code` longtext COLLATE utf8mb4_unicode_ci,
  `BCL` longtext COLLATE utf8mb4_unicode_ci,
  `BCLIR` longtext COLLATE utf8mb4_unicode_ci,
  `Graph` longtext COLLATE utf8mb4_unicode_ci,
  `Description` text COLLATE utf8mb4_unicode_ci,
  `Type` int DEFAULT NULL,
  `Category` int DEFAULT NULL,
  `Domain` int DEFAULT NULL,
  `Status` int DEFAULT NULL,
  `Priority` int DEFAULT NULL,
  `Severity` int DEFAULT NULL,
  `Group` int DEFAULT NULL,
  `CreatedAt` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`Id`),
  KEY `Priority` (`Priority`),
  KEY `Severity` (`Severity`),
  KEY `Group` (`Group`),
  KEY `idx_method_name` (`Name`),
  KEY `idx_method_type` (`Type`),
  KEY `idx_method_category` (`Category`),
  KEY `idx_method_domain` (`Domain`),
  KEY `idx_method_status` (`Status`),
  CONSTRAINT `method_ibfk_1` FOREIGN KEY (`Type`) REFERENCES `type` (`id`),
  CONSTRAINT `method_ibfk_2` FOREIGN KEY (`Category`) REFERENCES `category` (`id`),
  CONSTRAINT `method_ibfk_3` FOREIGN KEY (`Domain`) REFERENCES `domain` (`id`),
  CONSTRAINT `method_ibfk_4` FOREIGN KEY (`Status`) REFERENCES `status` (`id`),
  CONSTRAINT `method_ibfk_5` FOREIGN KEY (`Priority`) REFERENCES `priority` (`id`),
  CONSTRAINT `method_ibfk_6` FOREIGN KEY (`Severity`) REFERENCES `severity` (`id`),
  CONSTRAINT `method_ibfk_7` FOREIGN KEY (`Group`) REFERENCES `group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `pattern`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `pattern` (
  `id` int NOT NULL AUTO_INCREMENT,
  `pattern_code` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `pattern_name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `pattern_text` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `domain_id` int DEFAULT NULL,
  `category_id` int DEFAULT NULL,
  `status_id` int DEFAULT '42',
  `source` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT 'vbpack',
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
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `pattern_law`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `pattern_law` (
  `pattern_id` int NOT NULL,
  `law_id` int NOT NULL,
  `relationship` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'violates',
  `note` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT '',
  PRIMARY KEY (`pattern_id`,`law_id`,`relationship`),
  KEY `idx_plaw_law` (`law_id`),
  KEY `idx_plaw_rel` (`relationship`),
  CONSTRAINT `pattern_law_ibfk_1` FOREIGN KEY (`pattern_id`) REFERENCES `pattern` (`id`) ON DELETE CASCADE,
  CONSTRAINT `pattern_law_ibfk_2` FOREIGN KEY (`law_id`) REFERENCES `law` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `prevention`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `prevention` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `incident_id` bigint NOT NULL,
  `prevention_type` enum('guard','validation','detection','process') COLLATE utf8mb4_unicode_ci NOT NULL,
  `type_id` int DEFAULT NULL,
  `rule_text` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
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
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `priority`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `priority` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `level` int DEFAULT '0',
  `description` text COLLATE utf8mb4_unicode_ci,
  `sort_order` int DEFAULT '0',
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_pri_name` (`name`),
  KEY `idx_pri_name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=21 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `problem`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `problem` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `problem` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `problem_type` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `type_id` int DEFAULT NULL,
  `category` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT '',
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
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `problem_solution`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `problem_solution` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `problem_id` bigint NOT NULL,
  `solution` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `weight` decimal(3,2) DEFAULT '0.50',
  `auto_apply` tinyint(1) DEFAULT '0',
  `scope` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `fault_code` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `success_count` int DEFAULT '0',
  `failure_count` int DEFAULT '0',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_psol_problem` (`problem_id`),
  KEY `idx_psol_auto` (`auto_apply`),
  CONSTRAINT `problem_solution_ibfk_1` FOREIGN KEY (`problem_id`) REFERENCES `problem` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `question`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `question` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `question_text` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `fingerprint` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  `type_id` int DEFAULT NULL,
  `category_id` int DEFAULT NULL,
  `domain_id` int DEFAULT NULL,
  `group_id` int DEFAULT NULL,
  `category` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `domain` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `is_answered` tinyint(1) DEFAULT '0',
  `is_active` tinyint(1) DEFAULT '1',
  `occurrence_count` int DEFAULT '1',
  `source_db` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `source_table` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `source_id` bigint DEFAULT '0',
  `source_column` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT '',
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
) ENGINE=InnoDB AUTO_INCREMENT=150453 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `question_type`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `question_type` (
  `id` int NOT NULL AUTO_INCREMENT,
  `type_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `sort_order` int DEFAULT '0',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `type_name` (`type_name`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `report`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `report` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `title` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `incident_id` bigint DEFAULT NULL,
  `type_id` int DEFAULT NULL,
  `category_id` int DEFAULT NULL,
  `domain_id` int DEFAULT NULL,
  `status_id` int DEFAULT NULL,
  `severity_id` int DEFAULT NULL,
  `priority_id` int DEFAULT NULL,
  `group_id` int DEFAULT NULL,
  `rendered_text` text COLLATE utf8mb4_unicode_ci,
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
  CONSTRAINT `report_ibfk_10` FOREIGN KEY (`severity_id`) REFERENCES `severity` (`id`) ON DELETE SET NULL,
  CONSTRAINT `report_ibfk_11` FOREIGN KEY (`priority_id`) REFERENCES `priority` (`id`) ON DELETE SET NULL,
  CONSTRAINT `report_ibfk_12` FOREIGN KEY (`group_id`) REFERENCES `group` (`id`) ON DELETE SET NULL,
  CONSTRAINT `report_ibfk_6` FOREIGN KEY (`type_id`) REFERENCES `type` (`id`) ON DELETE SET NULL,
  CONSTRAINT `report_ibfk_7` FOREIGN KEY (`category_id`) REFERENCES `category` (`id`) ON DELETE SET NULL,
  CONSTRAINT `report_ibfk_8` FOREIGN KEY (`domain_id`) REFERENCES `domain` (`id`) ON DELETE SET NULL,
  CONSTRAINT `report_ibfk_9` FOREIGN KEY (`status_id`) REFERENCES `status` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `report_answer`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `report_answer` (
  `report_id` bigint NOT NULL,
  `answer_id` bigint NOT NULL,
  PRIMARY KEY (`report_id`,`answer_id`),
  KEY `idx_ra_answer` (`answer_id`),
  CONSTRAINT `report_answer_ibfk_1` FOREIGN KEY (`report_id`) REFERENCES `report` (`id`) ON DELETE CASCADE,
  CONSTRAINT `report_answer_ibfk_2` FOREIGN KEY (`answer_id`) REFERENCES `answer` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `report_cause`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `report_cause` (
  `report_id` bigint NOT NULL,
  `cause_id` bigint NOT NULL,
  PRIMARY KEY (`report_id`,`cause_id`),
  KEY `idx_rc_cause` (`cause_id`),
  CONSTRAINT `report_cause_ibfk_1` FOREIGN KEY (`report_id`) REFERENCES `report` (`id`) ON DELETE CASCADE,
  CONSTRAINT `report_cause_ibfk_2` FOREIGN KEY (`cause_id`) REFERENCES `cause` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `report_error`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `report_error` (
  `report_id` bigint NOT NULL,
  `error_id` bigint NOT NULL,
  `sort_order` int DEFAULT '0',
  PRIMARY KEY (`report_id`,`error_id`),
  KEY `idx_re_error` (`error_id`),
  CONSTRAINT `report_error_ibfk_1` FOREIGN KEY (`report_id`) REFERENCES `report` (`id`) ON DELETE CASCADE,
  CONSTRAINT `report_error_ibfk_2` FOREIGN KEY (`error_id`) REFERENCES `error` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `report_evidence`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `report_evidence` (
  `report_id` bigint NOT NULL,
  `evidence_id` bigint NOT NULL,
  PRIMARY KEY (`report_id`,`evidence_id`),
  KEY `idx_re_evidence` (`evidence_id`),
  CONSTRAINT `report_evidence_ibfk_1` FOREIGN KEY (`report_id`) REFERENCES `report` (`id`) ON DELETE CASCADE,
  CONSTRAINT `report_evidence_ibfk_2` FOREIGN KEY (`evidence_id`) REFERENCES `evidence` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `report_fact`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `report_fact` (
  `report_id` bigint NOT NULL,
  `fact_id` bigint NOT NULL,
  `sort_order` int DEFAULT '0',
  PRIMARY KEY (`report_id`,`fact_id`),
  KEY `idx_rf_fact` (`fact_id`),
  CONSTRAINT `report_fact_ibfk_1` FOREIGN KEY (`report_id`) REFERENCES `report` (`id`) ON DELETE CASCADE,
  CONSTRAINT `report_fact_ibfk_2` FOREIGN KEY (`fact_id`) REFERENCES `fact` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `report_fix`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `report_fix` (
  `report_id` bigint NOT NULL,
  `fix_id` bigint NOT NULL,
  `sort_order` int DEFAULT '0',
  PRIMARY KEY (`report_id`,`fix_id`),
  KEY `idx_rf_fix` (`fix_id`),
  CONSTRAINT `report_fix_ibfk_1` FOREIGN KEY (`report_id`) REFERENCES `report` (`id`) ON DELETE CASCADE,
  CONSTRAINT `report_fix_ibfk_2` FOREIGN KEY (`fix_id`) REFERENCES `fix` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `report_prevention`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `report_prevention` (
  `report_id` bigint NOT NULL,
  `prevention_id` bigint NOT NULL,
  PRIMARY KEY (`report_id`,`prevention_id`),
  KEY `idx_rprev_prevention` (`prevention_id`),
  CONSTRAINT `report_prevention_ibfk_1` FOREIGN KEY (`report_id`) REFERENCES `report` (`id`) ON DELETE CASCADE,
  CONSTRAINT `report_prevention_ibfk_2` FOREIGN KEY (`prevention_id`) REFERENCES `prevention` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `report_problem`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `report_problem` (
  `report_id` bigint NOT NULL,
  `problem_id` bigint NOT NULL,
  PRIMARY KEY (`report_id`,`problem_id`),
  KEY `idx_rp_problem` (`problem_id`),
  CONSTRAINT `report_problem_ibfk_1` FOREIGN KEY (`report_id`) REFERENCES `report` (`id`) ON DELETE CASCADE,
  CONSTRAINT `report_problem_ibfk_2` FOREIGN KEY (`problem_id`) REFERENCES `problem` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `report_question`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `report_question` (
  `report_id` bigint NOT NULL,
  `question_id` bigint NOT NULL,
  PRIMARY KEY (`report_id`,`question_id`),
  KEY `idx_rq_question` (`question_id`),
  CONSTRAINT `report_question_ibfk_1` FOREIGN KEY (`report_id`) REFERENCES `report` (`id`) ON DELETE CASCADE,
  CONSTRAINT `report_question_ibfk_2` FOREIGN KEY (`question_id`) REFERENCES `question` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `report_rule`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `report_rule` (
  `report_id` bigint NOT NULL,
  `rule_id` bigint NOT NULL,
  PRIMARY KEY (`report_id`,`rule_id`),
  KEY `idx_rr_rule` (`rule_id`),
  CONSTRAINT `report_rule_ibfk_1` FOREIGN KEY (`report_id`) REFERENCES `report` (`id`) ON DELETE CASCADE,
  CONSTRAINT `report_rule_ibfk_2` FOREIGN KEY (`rule_id`) REFERENCES `rule` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `rule`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `rule` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `pattern` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `trigger_condition` text COLLATE utf8mb4_unicode_ci,
  `fix_action` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `language` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `category` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT '',
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
  `source` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `source_origin` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `discovered_by` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT '',
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
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `severity`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `severity` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `level` int DEFAULT '0',
  `description` text COLLATE utf8mb4_unicode_ci,
  `sort_order` int DEFAULT '0',
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_sev_name` (`name`),
  KEY `idx_sev_name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=31 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `status`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `status` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `sort_order` int DEFAULT '0',
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_status_name` (`name`),
  KEY `idx_status_name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=46 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `table_column`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `table_column` (
  `id` int NOT NULL AUTO_INCREMENT,
  `table_id` int NOT NULL,
  `column_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `data_type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_nullable` tinyint(1) DEFAULT '1',
  `default_value` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `authority_table_id` int DEFAULT NULL,
  `is_completeness` tinyint(1) DEFAULT '0',
  `description` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_tc_table_col` (`table_id`,`column_name`),
  KEY `idx_tc_table` (`table_id`),
  KEY `idx_tc_authority` (`authority_table_id`),
  KEY `idx_tc_completeness` (`is_completeness`),
  CONSTRAINT `table_column_ibfk_1` FOREIGN KEY (`table_id`) REFERENCES `table_registry` (`id`) ON DELETE CASCADE,
  CONSTRAINT `table_column_ibfk_2` FOREIGN KEY (`authority_table_id`) REFERENCES `table_registry` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=386 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `table_registry`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `table_registry` (
  `id` int NOT NULL AUTO_INCREMENT,
  `table_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `display_name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `purpose` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `description` text COLLATE utf8mb4_unicode_ci,
  `type_id` int DEFAULT NULL,
  `owner` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `primary_key` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT 'id',
  `is_active` tinyint(1) DEFAULT '1',
  `version` int DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `table_name` (`table_name`),
  KEY `idx_treg_name` (`table_name`),
  KEY `idx_treg_type` (`type_id`),
  KEY `idx_treg_active` (`is_active`),
  CONSTRAINT `table_registry_ibfk_1` FOREIGN KEY (`type_id`) REFERENCES `type` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=47 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `table_relationship`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `table_relationship` (
  `id` int NOT NULL AUTO_INCREMENT,
  `parent_table_id` int NOT NULL,
  `child_table_id` int NOT NULL,
  `relationship_type` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '1:N',
  `fk_column` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `on_delete` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT 'RESTRICT',
  `description` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_tr_parent_child_fk` (`parent_table_id`,`child_table_id`,`fk_column`),
  KEY `idx_tr_parent` (`parent_table_id`),
  KEY `idx_tr_child` (`child_table_id`),
  KEY `idx_tr_type` (`relationship_type`),
  CONSTRAINT `table_relationship_ibfk_1` FOREIGN KEY (`parent_table_id`) REFERENCES `table_registry` (`id`) ON DELETE CASCADE,
  CONSTRAINT `table_relationship_ibfk_2` FOREIGN KEY (`child_table_id`) REFERENCES `table_registry` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=129 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `table_rule`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `table_rule` (
  `id` int NOT NULL AUTO_INCREMENT,
  `table_id` int NOT NULL,
  `law_id` int DEFAULT NULL,
  `pattern_id` int DEFAULT NULL,
  `rule_text` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_required` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_trule_table_law` (`table_id`,`law_id`),
  UNIQUE KEY `uq_trule_table_pattern` (`table_id`,`pattern_id`),
  KEY `idx_trule_table` (`table_id`),
  KEY `idx_trule_law` (`law_id`),
  KEY `idx_trule_pattern` (`pattern_id`),
  CONSTRAINT `table_rule_ibfk_1` FOREIGN KEY (`table_id`) REFERENCES `table_registry` (`id`) ON DELETE CASCADE,
  CONSTRAINT `table_rule_ibfk_2` FOREIGN KEY (`law_id`) REFERENCES `law` (`id`) ON DELETE SET NULL,
  CONSTRAINT `table_rule_ibfk_3` FOREIGN KEY (`pattern_id`) REFERENCES `pattern` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=115 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
DROP TABLE IF EXISTS `type`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `type` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `sort_order` int DEFAULT '0',
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_type_name` (`name`),
  KEY `idx_type_name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=140 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

