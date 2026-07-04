-- diagnostic_kb schema — unified diagnostic knowledge base
-- Centered on INCIDENT as the anchor. Everything hangs off it.
-- Design: 2026-07-02, session: report-domain

-- ─── INCIDENT (the anchor) ─────────────────────────────────────
-- One row per operation execution. This IS the report made persistent.
CREATE TABLE incident (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    operation       VARCHAR(200) NOT NULL,
    source          VARCHAR(200) DEFAULT '',
    result          ENUM('ok','fail','partial') NOT NULL,
    reason          TEXT,
    fact_count      INT DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finalized_at    TIMESTAMP NULL DEFAULT NULL,
    INDEX idx_incident_operation (operation),
    INDEX idx_incident_result (result),
    INDEX idx_incident_created (created_at)
) ENGINE=InnoDB;

-- ─── FACT (entity — a fact. incident_id is the relationship.) ─
CREATE TABLE IF NOT EXISTS fact (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    incident_id     BIGINT NOT NULL,
    slot            VARCHAR(50) NOT NULL,
    kind            VARCHAR(50) NOT NULL,
    name            VARCHAR(200) NOT NULL,
    value           TEXT,
    severity        VARCHAR(20) DEFAULT '',
    unit            VARCHAR(50) DEFAULT '',
    detail          TEXT,
    timestamp       VARCHAR(50) DEFAULT '',
    source          VARCHAR(200) DEFAULT '',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (incident_id) REFERENCES incident(id) ON DELETE CASCADE,
    INDEX idx_fact_incident (incident_id),
    INDEX idx_fact_slot (slot),
    INDEX idx_fact_kind (kind)
) ENGINE=InnoDB;

-- ─── ANSWER (answers to the 19 diagnostic questions) ───────────
CREATE TABLE answer (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    incident_id     BIGINT NOT NULL,
    category        VARCHAR(50) NOT NULL,
    question        VARCHAR(100) NOT NULL,
    status          ENUM('known','unknown','pending','n/a') NOT NULL,
    answer          TEXT,
    source_type     VARCHAR(50) DEFAULT 'report',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (incident_id) REFERENCES incident(id) ON DELETE CASCADE,
    INDEX idx_answer_incident (incident_id),
    INDEX idx_answer_category (category),
    INDEX idx_answer_status (status)
) ENGINE=InnoDB;

-- ─── CAUSE (causes identified for an incident) ─────────────────
CREATE TABLE cause (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    incident_id     BIGINT NOT NULL,
    cause_type      ENUM('root','contributing','runtime','behavioral') NOT NULL,
    cause_text      TEXT NOT NULL,
    severity        INT DEFAULT 0,
    evidence        TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (incident_id) REFERENCES incident(id) ON DELETE CASCADE,
    INDEX idx_cause_incident (incident_id),
    INDEX idx_cause_type (cause_type)
) ENGINE=InnoDB;

-- ─── FIX (fixes attempted for an incident) ─────────────────────
CREATE TABLE fix (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    incident_id     BIGINT NOT NULL,
    fix_type        ENUM('auto','manual','recommended') NOT NULL,
    fix_action      TEXT NOT NULL,
    result          ENUM('success','failed','partial','untried') DEFAULT 'untried',
    confidence      DECIMAL(3,2) DEFAULT 0.00,
    before_hash     VARCHAR(64) DEFAULT '',
    after_hash      VARCHAR(64) DEFAULT '',
    applied_at      TIMESTAMP NULL DEFAULT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (incident_id) REFERENCES incident(id) ON DELETE CASCADE,
    INDEX idx_fix_incident (incident_id),
    INDEX idx_fix_result (result)
) ENGINE=InnoDB;

-- ─── PREVENTION (prevention rules derived from an incident) ────
CREATE TABLE prevention (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    incident_id     BIGINT NOT NULL,
    prevention_type ENUM('guard','validation','detection','process') NOT NULL,
    rule_text       TEXT NOT NULL,
    description     TEXT,
    is_active       TINYINT(1) DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (incident_id) REFERENCES incident(id) ON DELETE CASCADE,
    INDEX idx_prev_incident (incident_id),
    INDEX idx_prev_active (is_active)
) ENGINE=InnoDB;

-- ─── EVIDENCE (supporting data for an incident) ────────────────
CREATE TABLE evidence (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    incident_id     BIGINT NOT NULL,
    evidence_type   VARCHAR(50) NOT NULL,
    source_file     VARCHAR(500) DEFAULT '',
    source_line     INT DEFAULT 0,
    content         TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (incident_id) REFERENCES incident(id) ON DELETE CASCADE,
    INDEX idx_evidence_incident (incident_id),
    INDEX idx_evidence_type (evidence_type)
) ENGINE=InnoDB;

-- ─── PROBLEM (generalized from incidents — type-level) ─────────
CREATE TABLE problem (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    problem         VARCHAR(500) NOT NULL,
    description     TEXT,
    problem_type    VARCHAR(100) DEFAULT '',
    category        VARCHAR(100) DEFAULT '',
    first_seen      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    occurrence_count INT DEFAULT 1,
    INDEX idx_problem_name (problem(100)),
    INDEX idx_problem_category (category)
) ENGINE=InnoDB;

-- ─── PROBLEM_SOLUTION (known solutions for a problem type) ─────
CREATE TABLE problem_solution (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    problem_id      BIGINT NOT NULL,
    solution        TEXT NOT NULL,
    weight          DECIMAL(3,2) DEFAULT 0.50,
    auto_apply      TINYINT(1) DEFAULT 0,
    scope           VARCHAR(100) DEFAULT '',
    fault_code      VARCHAR(100) DEFAULT '',
    success_count   INT DEFAULT 0,
    failure_count   INT DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (problem_id) REFERENCES problem(id) ON DELETE CASCADE,
    INDEX idx_psol_problem (problem_id),
    INDEX idx_psol_auto (auto_apply)
) ENGINE=InnoDB;

-- ─── RULE (entity — a rule. source_origin records how obtained.) ─
CREATE TABLE IF NOT EXISTS rule (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    pattern         TEXT NOT NULL,
    trigger_condition TEXT,
    fix_action      TEXT NOT NULL,
    language        VARCHAR(20) DEFAULT '',
    category        VARCHAR(50) DEFAULT '',
    severity        INT DEFAULT 0,
    confidence      DECIMAL(5,2) DEFAULT 0.00,
    success_count   INT DEFAULT 0,
    failure_count   INT DEFAULT 0,
    source          VARCHAR(100) DEFAULT '',
    problem_id      BIGINT NULL DEFAULT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used       TIMESTAMP NULL DEFAULT NULL,
    FOREIGN KEY (problem_id) REFERENCES problem(id) ON DELETE SET NULL,
    INDEX idx_rule_pattern (pattern(100)),
    INDEX idx_rule_category (category),
    INDEX idx_rule_confidence (confidence)
) ENGINE=InnoDB;

-- ════════════════════════════════════════════════════════════════
-- UNIVERSAL AUTHORITY TABLES
-- ════════════════════════════════════════════════════════════════
-- Architectural rule: One concept. One authority. One table.
-- No subsystem may create its own lookup table for a concept that
-- already has an authority. All tables FK to these.
-- The 'kind' column distinguishes what the entry classifies.
-- ════════════════════════════════════════════════════════════════

-- ─── TYPE (universal) ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS type (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    kind            VARCHAR(100) NOT NULL,
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    sort_order      INT DEFAULT 0,
    is_active       TINYINT(1) DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_type_kind_name (kind, name),
    INDEX idx_type_kind (kind),
    INDEX idx_type_name (name)
) ENGINE=InnoDB;

-- ─── CATEGORY (universal) ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS category (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    kind            VARCHAR(100) NOT NULL,
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    parent_id       INT NULL DEFAULT NULL,
    sort_order      INT DEFAULT 0,
    is_active       TINYINT(1) DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_cat_kind_name (kind, name),
    INDEX idx_cat_kind (kind),
    INDEX idx_cat_name (name),
    INDEX idx_cat_parent (parent_id),
    FOREIGN KEY (parent_id) REFERENCES category(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ─── DOMAIN (universal) ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS domain (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    kind            VARCHAR(100) NOT NULL,
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    sort_order      INT DEFAULT 0,
    is_active       TINYINT(1) DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_dom_kind_name (kind, name),
    INDEX idx_dom_kind (kind),
    INDEX idx_dom_name (name)
) ENGINE=InnoDB;

-- ─── STATUS (universal) ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS status (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    kind            VARCHAR(100) NOT NULL,
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    sort_order      INT DEFAULT 0,
    is_active       TINYINT(1) DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_status_kind_name (kind, name),
    INDEX idx_status_kind (kind),
    INDEX idx_status_name (name)
) ENGINE=InnoDB;

-- ─── SEVERITY (universal) ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS severity (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    kind            VARCHAR(100) NOT NULL,
    name            VARCHAR(200) NOT NULL,
    level           INT DEFAULT 0,
    description     TEXT,
    sort_order      INT DEFAULT 0,
    is_active       TINYINT(1) DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_sev_kind_name (kind, name),
    INDEX idx_sev_kind (kind),
    INDEX idx_sev_name (name)
) ENGINE=InnoDB;

-- ─── PRIORITY (universal) ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS priority (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    kind            VARCHAR(100) NOT NULL,
    name            VARCHAR(200) NOT NULL,
    level           INT DEFAULT 0,
    description     TEXT,
    sort_order      INT DEFAULT 0,
    is_active       TINYINT(1) DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_pri_kind_name (kind, name),
    INDEX idx_pri_kind (kind),
    INDEX idx_pri_name (name)
) ENGINE=InnoDB;

-- ─── GROUP (universal) ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `group` (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    kind            VARCHAR(100) NOT NULL,
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    parent_id       INT NULL DEFAULT NULL,
    sort_order      INT DEFAULT 0,
    is_active       TINYINT(1) DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_grp_kind_name (kind, name),
    INDEX idx_grp_kind (kind),
    INDEX idx_grp_name (name),
    INDEX idx_grp_parent (parent_id),
    FOREIGN KEY (parent_id) REFERENCES `group`(id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ─── QUESTION (migrated from all databases) ───────────────────
CREATE TABLE IF NOT EXISTS question (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    question_text   TEXT NOT NULL,
    fingerprint     VARCHAR(32) NOT NULL UNIQUE,
    type_id         INT NULL DEFAULT NULL,
    category_id     INT NULL DEFAULT NULL,
    domain_id       INT NULL DEFAULT NULL,
    group_id        INT NULL DEFAULT NULL,
    is_answered     TINYINT(1) DEFAULT 0,
    is_active       TINYINT(1) DEFAULT 1,
    occurrence_count INT DEFAULT 1,
    source_db       VARCHAR(100) DEFAULT '',
    source_table    VARCHAR(100) DEFAULT '',
    source_id       BIGINT DEFAULT 0,
    source_column   VARCHAR(100) DEFAULT '',
    migrated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (type_id) REFERENCES type(id) ON DELETE SET NULL,
    FOREIGN KEY (category_id) REFERENCES category(id) ON DELETE SET NULL,
    FOREIGN KEY (domain_id) REFERENCES domain(id) ON DELETE SET NULL,
    FOREIGN KEY (group_id) REFERENCES `group`(id) ON DELETE SET NULL,
    INDEX idx_question_fp (fingerprint),
    INDEX idx_question_type (type_id),
    INDEX idx_question_category (category_id),
    INDEX idx_question_domain (domain_id),
    INDEX idx_question_group (group_id),
    INDEX idx_question_answered (is_answered),
    INDEX idx_question_source (source_db, source_table)
) ENGINE=InnoDB;

-- ─── QUESTION_TYPE (legacy — will be replaced by type table) ───
CREATE TABLE IF NOT EXISTS question_type (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    type_name       VARCHAR(100) NOT NULL UNIQUE,
    description     TEXT,
    sort_order      INT DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ─── INCIDENT_PROBLEM (links incidents to problem types) ───────
CREATE TABLE incident_problem (
    incident_id     BIGINT NOT NULL,
    problem_id      BIGINT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (incident_id, problem_id),
    FOREIGN KEY (incident_id) REFERENCES incident(id) ON DELETE CASCADE,
    FOREIGN KEY (problem_id) REFERENCES problem(id) ON DELETE CASCADE,
    INDEX idx_iproblem_problem (problem_id)
) ENGINE=InnoDB;

-- ─── LAW (architectural truths — what AI must always know) ──────
-- A law is a principle that affects every design decision.
-- NOT a coding rule. An architectural truth. One row = one law.
-- Uses authority FKs (domain, category, status, priority).
CREATE TABLE IF NOT EXISTS law (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    law_code        VARCHAR(20) NOT NULL UNIQUE,
    law_name        VARCHAR(200) NOT NULL,
    law_text        TEXT NOT NULL,
    domain_id       INT,
    category_id     INT,
    status_id       INT DEFAULT 42,
    priority_id     INT DEFAULT 12,
    source          VARCHAR(200) DEFAULT 'conversation',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (domain_id) REFERENCES domain(id),
    FOREIGN KEY (category_id) REFERENCES category(id),
    FOREIGN KEY (status_id) REFERENCES status(id),
    FOREIGN KEY (priority_id) REFERENCES priority(id),
    INDEX idx_law_code (law_code),
    INDEX idx_law_domain (domain_id),
    INDEX idx_law_category (category_id)
) ENGINE=InnoDB;

-- ─── PATTERN (forbidden or recommended implementation patterns) ─
-- A pattern is a concrete implementation choice.
-- category_id: 'forbidden' (violates a law) or 'recommended' (satisfies a law)
-- A pattern is NOT a law. It is the thing to avoid or encourage.
CREATE TABLE IF NOT EXISTS pattern (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    pattern_code    VARCHAR(20) NOT NULL UNIQUE,
    pattern_name    VARCHAR(200) NOT NULL,
    pattern_text    TEXT NOT NULL,
    domain_id       INT,
    category_id     INT,
    status_id       INT DEFAULT 42,
    source          VARCHAR(200) DEFAULT 'vbpack',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (domain_id) REFERENCES domain(id),
    FOREIGN KEY (category_id) REFERENCES category(id),
    FOREIGN KEY (status_id) REFERENCES status(id),
    INDEX idx_pattern_code (pattern_code),
    INDEX idx_pattern_category (category_id),
    INDEX idx_pattern_domain (domain_id)
) ENGINE=InnoDB;

-- ─── PATTERN_LAW (which laws each pattern violates or satisfies) ─
-- The reasoning graph. AI can trace:
--   "I'm about to use a decorator" → DEC → violates → LAW5
CREATE TABLE IF NOT EXISTS pattern_law (
    pattern_id      INT NOT NULL,
    law_id          INT NOT NULL,
    relationship    VARCHAR(20) NOT NULL DEFAULT 'violates',
    note            VARCHAR(200) DEFAULT '',
    PRIMARY KEY (pattern_id, law_id, relationship),
    FOREIGN KEY (pattern_id) REFERENCES pattern(id) ON DELETE CASCADE,
    FOREIGN KEY (law_id) REFERENCES law(id) ON DELETE CASCADE,
    INDEX idx_plaw_law (law_id),
    INDEX idx_plaw_rel (relationship)
) ENGINE=InnoDB;

-- ─── DECISION (records of why a design choice was made) ─────────
-- A decision is a historical record. It documents WHY, not WHAT.
CREATE TABLE IF NOT EXISTS decision (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    decision_code   VARCHAR(50) NOT NULL UNIQUE,
    decision_name   VARCHAR(200) NOT NULL,
    context         TEXT NOT NULL,
    choice          TEXT NOT NULL,
    rationale       TEXT NOT NULL,
    domain_id       INT,
    status_id       INT DEFAULT 42,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (domain_id) REFERENCES domain(id),
    FOREIGN KEY (status_id) REFERENCES status(id),
    INDEX idx_decision_code (decision_code),
    INDEX idx_decision_domain (domain_id)
) ENGINE=InnoDB;

-- ════════════════════════════════════════════════════════════════
-- SELF-DESCRIBING SCHEMA — the database describes itself
-- Four meta-tables. Each has one responsibility.
-- They obey the same architecture they describe.
-- ════════════════════════════════════════════════════════════════

-- ─── TABLE_REGISTRY — one row per table; what the table is ──────
CREATE TABLE IF NOT EXISTS table_registry (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    table_name      VARCHAR(100) NOT NULL UNIQUE,
    display_name    VARCHAR(200) NOT NULL DEFAULT '',
    purpose         VARCHAR(500) NOT NULL DEFAULT '',
    description     TEXT,
    type_id         INT DEFAULT NULL,
    owner           VARCHAR(100) DEFAULT '',
    primary_key     VARCHAR(100) DEFAULT 'id',
    is_active       TINYINT(1) DEFAULT 1,
    version         INT DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (type_id) REFERENCES type(id) ON DELETE SET NULL,
    INDEX idx_treg_name (table_name),
    INDEX idx_treg_type (type_id),
    INDEX idx_treg_active (is_active)
) ENGINE=InnoDB;

-- ─── TABLE_COLUMN — one row per column; what each column means ───
-- authority_table_id: if this column is an FK to an authority, which table_registry row?
-- is_completeness: is this column part of the completeness contract (an authority FK)?
CREATE TABLE IF NOT EXISTS table_column (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    table_id        INT NOT NULL,
    column_name     VARCHAR(100) NOT NULL,
    data_type       VARCHAR(50) NOT NULL,
    is_nullable     TINYINT(1) DEFAULT 1,
    default_value   VARCHAR(200) DEFAULT '',
    authority_table_id INT DEFAULT NULL,
    is_completeness TINYINT(1) DEFAULT 0,
    description     VARCHAR(500) DEFAULT '',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (table_id) REFERENCES table_registry(id) ON DELETE CASCADE,
    FOREIGN KEY (authority_table_id) REFERENCES table_registry(id) ON DELETE SET NULL,
    UNIQUE KEY uq_tc_table_col (table_id, column_name),
    INDEX idx_tc_table (table_id),
    INDEX idx_tc_authority (authority_table_id),
    INDEX idx_tc_completeness (is_completeness)
) ENGINE=InnoDB;

-- ─── TABLE_RELATIONSHIP — one row per FK; how tables connect ────
CREATE TABLE IF NOT EXISTS table_relationship (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    parent_table_id INT NOT NULL,
    child_table_id  INT NOT NULL,
    relationship_type VARCHAR(10) NOT NULL DEFAULT '1:N',
    fk_column       VARCHAR(100) NOT NULL DEFAULT '',
    on_delete       VARCHAR(20) DEFAULT 'RESTRICT',
    description     VARCHAR(500) DEFAULT '',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_table_id) REFERENCES table_registry(id) ON DELETE CASCADE,
    FOREIGN KEY (child_table_id) REFERENCES table_registry(id) ON DELETE CASCADE,
    UNIQUE KEY uq_tr_parent_child_fk (parent_table_id, child_table_id, fk_column),
    INDEX idx_tr_parent (parent_table_id),
    INDEX idx_tr_child (child_table_id),
    INDEX idx_tr_type (relationship_type)
) ENGINE=InnoDB;

-- ─── TABLE_RULE — which laws apply to which table ───────────────
-- Links table_registry to law and pattern. AI can ask:
-- "What laws apply to the error table?"
CREATE TABLE IF NOT EXISTS table_rule (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    table_id        INT NOT NULL,
    law_id          INT DEFAULT NULL,
    pattern_id      INT DEFAULT NULL,
    rule_text       VARCHAR(500) NOT NULL,
    is_required     TINYINT(1) DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (table_id) REFERENCES table_registry(id) ON DELETE CASCADE,
    FOREIGN KEY (law_id) REFERENCES law(id) ON DELETE SET NULL,
    FOREIGN KEY (pattern_id) REFERENCES pattern(id) ON DELETE SET NULL,
    UNIQUE KEY uq_trule_table_law (table_id, law_id),
    UNIQUE KEY uq_trule_table_pattern (table_id, pattern_id),
    INDEX idx_trule_table (table_id),
    INDEX idx_trule_law (law_id),
    INDEX idx_trule_pattern (pattern_id)
) ENGINE=InnoDB;

-- ════════════════════════════════════════════════════════════════
-- CODE STRUCTURE — Method, ComputationUnit, Class
-- Naming convention: PascalCase, no underscores.
-- Authority FKs: Type, Category, Domain, Status, Priority, Severity, Group
-- Representations: Code, BCL, BCLIR, Graph, Description
-- Never create a specialized version of a universal concept.
-- ════════════════════════════════════════════════════════════════

-- ─── METHOD — the smallest executable unit ──────────────────────
CREATE TABLE IF NOT EXISTS Method (
    Id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    Name            VARCHAR(200) NOT NULL,
    Signature       TEXT,
    Code            LONGTEXT,
    BCL             LONGTEXT,
    BCLIR           LONGTEXT,
    Graph           LONGTEXT,
    Description     TEXT,
    Type            INT DEFAULT NULL,
    Category        INT DEFAULT NULL,
    Domain          INT DEFAULT NULL,
    Status          INT DEFAULT NULL,
    Priority        INT DEFAULT NULL,
    Severity        INT DEFAULT NULL,
    `Group`         INT DEFAULT NULL,
    CreatedAt       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (Type) REFERENCES type(id),
    FOREIGN KEY (Category) REFERENCES category(id),
    FOREIGN KEY (Domain) REFERENCES domain(id),
    FOREIGN KEY (Status) REFERENCES status(id),
    FOREIGN KEY (Priority) REFERENCES priority(id),
    FOREIGN KEY (Severity) REFERENCES severity(id),
    FOREIGN KEY (`Group`) REFERENCES `group`(id),
    INDEX idx_method_name (Name),
    INDEX idx_method_type (Type),
    INDEX idx_method_category (Category),
    INDEX idx_method_domain (Domain),
    INDEX idx_method_status (Status)
) ENGINE=InnoDB;

-- ─── COMPUTATIONUNIT — a composition of methods ─────────────────
CREATE TABLE IF NOT EXISTS ComputationUnit (
    Id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    Name            VARCHAR(200) NOT NULL,
    Code            LONGTEXT,
    BCL             LONGTEXT,
    BCLIR           LONGTEXT,
    Graph           LONGTEXT,
    Description     TEXT,
    Type            INT DEFAULT NULL,
    Category        INT DEFAULT NULL,
    Domain          INT DEFAULT NULL,
    Status          INT DEFAULT NULL,
    Priority        INT DEFAULT NULL,
    Severity        INT DEFAULT NULL,
    `Group`         INT DEFAULT NULL,
    CreatedAt       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (Type) REFERENCES type(id),
    FOREIGN KEY (Category) REFERENCES category(id),
    FOREIGN KEY (Domain) REFERENCES domain(id),
    FOREIGN KEY (Status) REFERENCES status(id),
    FOREIGN KEY (Priority) REFERENCES priority(id),
    FOREIGN KEY (Severity) REFERENCES severity(id),
    FOREIGN KEY (`Group`) REFERENCES `group`(id),
    INDEX idx_cu_name (Name),
    INDEX idx_cu_type (Type),
    INDEX idx_cu_domain (Domain)
) ENGINE=InnoDB;

-- ─── CLASS — a composition of computation units ─────────────────
CREATE TABLE IF NOT EXISTS Class (
    Id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    Name            VARCHAR(200) NOT NULL,
    Code            LONGTEXT,
    BCL             LONGTEXT,
    BCLIR           LONGTEXT,
    Graph           LONGTEXT,
    Description     TEXT,
    Type            INT DEFAULT NULL,
    Category        INT DEFAULT NULL,
    Domain          INT DEFAULT NULL,
    Status          INT DEFAULT NULL,
    Priority        INT DEFAULT NULL,
    Severity        INT DEFAULT NULL,
    `Group`         INT DEFAULT NULL,
    CreatedAt       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (Type) REFERENCES type(id),
    FOREIGN KEY (Category) REFERENCES category(id),
    FOREIGN KEY (Domain) REFERENCES domain(id),
    FOREIGN KEY (Status) REFERENCES status(id),
    FOREIGN KEY (Priority) REFERENCES priority(id),
    FOREIGN KEY (Severity) REFERENCES severity(id),
    FOREIGN KEY (`Group`) REFERENCES `group`(id),
    INDEX idx_class_name (Name),
    INDEX idx_class_type (Type),
    INDEX idx_class_domain (Domain)
) ENGINE=InnoDB;

-- ─── COMPUTATIONUNITMETHOD — M:N join ───────────────────────────
-- A computation unit is composed of methods. Sequence orders them.
-- Role describes what the method does in this unit.
CREATE TABLE IF NOT EXISTS ComputationUnitMethod (
    ComputationUnit BIGINT NOT NULL,
    Method          BIGINT NOT NULL,
    Sequence        INT DEFAULT 0,
    Role            VARCHAR(100) DEFAULT '',
    PRIMARY KEY (ComputationUnit, Method),
    FOREIGN KEY (ComputationUnit) REFERENCES ComputationUnit(Id) ON DELETE CASCADE,
    FOREIGN KEY (Method) REFERENCES Method(Id) ON DELETE CASCADE,
    INDEX idx_cum_method (Method),
    INDEX idx_cum_sequence (Sequence)
) ENGINE=InnoDB;

-- ─── CLASSCOMPUTATIONUNIT — M:N join ────────────────────────────
-- A class is composed of computation units. Sequence orders them.
CREATE TABLE IF NOT EXISTS ClassComputationUnit (
    Class           BIGINT NOT NULL,
    ComputationUnit BIGINT NOT NULL,
    Sequence        INT DEFAULT 0,
    PRIMARY KEY (Class, ComputationUnit),
    FOREIGN KEY (Class) REFERENCES Class(Id) ON DELETE CASCADE,
    FOREIGN KEY (ComputationUnit) REFERENCES ComputationUnit(Id) ON DELETE CASCADE,
    INDEX idx_ccu_unit (ComputationUnit),
    INDEX idx_ccu_sequence (Sequence)
) ENGINE=InnoDB;

-- ════════════════════════════════════════════════════════════════
-- PAIRED REASONING — Complement Relationships (Yin/Yang)
-- Every knowledge object can have a complement.
-- The complement is a RELATIONSHIP, not a TYPE.
-- The Type authority defines what kind of relationship (complement,
-- contradiction, refinement, prerequisite, broader, consequence,
-- supports, challenges).
-- ════════════════════════════════════════════════════════════════

-- ─── QUESTIONRELATION — relationships between questions ────────
CREATE TABLE IF NOT EXISTS QuestionRelation (
    Id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    Question        BIGINT NOT NULL,
    RelatedQuestion BIGINT NOT NULL,
    Type            INT NOT NULL,
    Note            VARCHAR(500) DEFAULT '',
    CreatedAt       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (Question) REFERENCES question(id) ON DELETE CASCADE,
    FOREIGN KEY (RelatedQuestion) REFERENCES question(id) ON DELETE CASCADE,
    FOREIGN KEY (Type) REFERENCES type(id),
    UNIQUE KEY uq_qr_pair (Question, RelatedQuestion, Type),
    INDEX idx_qr_question (Question),
    INDEX idx_qr_related (RelatedQuestion),
    INDEX idx_qr_type (Type)
) ENGINE=InnoDB;

-- ─── ANSWERRELATION — relationships between answers ────────────
CREATE TABLE IF NOT EXISTS AnswerRelation (
    Id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    Answer          BIGINT NOT NULL,
    RelatedAnswer   BIGINT NOT NULL,
    Type            INT NOT NULL,
    Note            VARCHAR(500) DEFAULT '',
    CreatedAt       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (Answer) REFERENCES answer(id) ON DELETE CASCADE,
    FOREIGN KEY (RelatedAnswer) REFERENCES answer(id) ON DELETE CASCADE,
    FOREIGN KEY (Type) REFERENCES type(id),
    UNIQUE KEY uq_ar_pair (Answer, RelatedAnswer, Type),
    INDEX idx_ar_answer (Answer),
    INDEX idx_ar_related (RelatedAnswer),
    INDEX idx_ar_type (Type)
) ENGINE=InnoDB;

-- ─── EVIDENCERELATION — relationships between evidence ─────────
-- This is where "evidence for" ↔ "evidence against" lives
CREATE TABLE IF NOT EXISTS EvidenceRelation (
    Id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    Evidence        BIGINT NOT NULL,
    RelatedEvidence BIGINT NOT NULL,
    Type            INT NOT NULL,
    Note            VARCHAR(500) DEFAULT '',
    CreatedAt       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (Evidence) REFERENCES evidence(id) ON DELETE CASCADE,
    FOREIGN KEY (RelatedEvidence) REFERENCES evidence(id) ON DELETE CASCADE,
    FOREIGN KEY (Type) REFERENCES type(id),
    UNIQUE KEY uq_er_pair (Evidence, RelatedEvidence, Type),
    INDEX idx_er_evidence (Evidence),
    INDEX idx_er_related (RelatedEvidence),
    INDEX idx_er_type (Type)
) ENGINE=InnoDB;

-- ─── FACTRELATION — relationships between facts ────────────────
-- "known" ↔ "unknown", "observed" ↔ "inferred"
CREATE TABLE IF NOT EXISTS FactRelation (
    Id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    Fact            BIGINT NOT NULL,
    RelatedFact     BIGINT NOT NULL,
    Type            INT NOT NULL,
    Note            VARCHAR(500) DEFAULT '',
    CreatedAt       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (Fact) REFERENCES fact(id) ON DELETE CASCADE,
    FOREIGN KEY (RelatedFact) REFERENCES fact(id) ON DELETE CASCADE,
    FOREIGN KEY (Type) REFERENCES type(id),
    UNIQUE KEY uq_fr_pair (Fact, RelatedFact, Type),
    INDEX idx_fr_fact (Fact),
    INDEX idx_fr_related (RelatedFact),
    INDEX idx_fr_type (Type)
) ENGINE=InnoDB;

-- ─── RULERELATION — relationships between rules ────────────────
-- "rule" ↔ "exception"
CREATE TABLE IF NOT EXISTS RuleRelation (
    Id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    Rule            BIGINT NOT NULL,
    RelatedRule     BIGINT NOT NULL,
    Type            INT NOT NULL,
    Note            VARCHAR(500) DEFAULT '',
    CreatedAt       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (Rule) REFERENCES rule(id) ON DELETE CASCADE,
    FOREIGN KEY (RelatedRule) REFERENCES rule(id) ON DELETE CASCADE,
    FOREIGN KEY (Type) REFERENCES type(id),
    UNIQUE KEY uq_rr_pair (Rule, RelatedRule, Type),
    INDEX idx_rr_rule (Rule),
    INDEX idx_rr_related (RelatedRule),
    INDEX idx_rr_type (Type)
) ENGINE=InnoDB;
