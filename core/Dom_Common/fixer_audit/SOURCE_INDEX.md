#[@GHOST]{file_path="core/Dom_Common/fixer_audit/SOURCE_INDEX.md" date="2026-07-04" author="Devin" session_id="inram-fixer-audit" context="Index of all in-RAM error fixer code versions across MySQL + filesystem"}
#[@VBSTYLE]{standard="VBStyle" version="1"}
#[@SUMMARY]{summary="Master index of every error fixer / bug fixer / repair engine version found across CODEBASE MySQL, vb_code_test, vb_shared, and filesystem"}
#[@CLASS]{class="FixerAudit"}
#[@METHOD]{method="SourceIndex"}

# In-RAM Error Fixer — All Versions Found

## TIER 1: CORE IN-RAM ERROR FIXERS (the ones you remember)

### C — In-RAM Error Detection & Correction
| ID  | File                    | Location                                          | Status    |
|-----|-------------------------|---------------------------------------------------|-----------|
| 2757| lib_errorFixer.h        | Vdive2UNIFIED_LIB/                                | HEADER    |
| 2832| lib_errorfixer.c        | Vdive2UNIFIED_LIB/ARCHIVE/                        | ORIGINAL  |
| 2891| lib_lib_errorfixer.c    | Vdive2UNIFIED_LIB/                                | WRAPPER v1|
| 2927| lib_workspace_lib_errorfixer.c | Vdive2UNIFIED_LIB/                         | WRAPPER v2|
| 3080| lib_lib_memoryfixer.c   | Vdive2UNIFIED_LIB/                                | MEMORY v1 |
| 2860| lib_memoryfixer.c       | Vdive2UNIFIED_LIB/ARCHIVE/                        | MEMORY v2 |
| 2784| thread_fixed.c          | Vdive2UNIFIED_LIB/ARCHIVE/                        | THREAD    |
| 2817| fixed_code_example.c    | Vdive2UNIFIED_LIB/ARCHIVE/                        | EXAMPLE   |

### Python — In-RAM Bug Fixer (UNIT_CODE_BUGFIX)
| DB               | Class                       | ID  | Description                                  |
|------------------|-----------------------------|-----|----------------------------------------------|
| vb_code_test     | UNIT_CODE_BUGFIX            | 1550| 6 strategies, :memory: SQLite, parallel     |
| vb_code_test     | VBStyleAutoFix              | 1615| SQLite, snapshots, header injection, audit  |
| vb_code_test     | ClassFixClassificationTester| 1063| Test harness for fix classifier              |
| vb_code_test     | InRamScanStore              | 930 | :memory: SQLite scan store                   |

### Python — AI Repair Services (Cascade_Tools)
| File                                   | Purpose                              |
|----------------------------------------|--------------------------------------|
| _Cls_Ai_ai_repair_service.py           | AI repair service                    |
| _Cls_Ai_code_repair_assistant.py       | Code repair assistant                |
| _Cls_Ai_code_repair_engine.py          | Code repair engine                   |
| _Cls_Ai_init_repair_db.py              | Repair DB initializer                |

## TIER 2: REPAIR ENGINES (related but different lineage)

| DB           | Class                            | ID  | Purpose                              |
|--------------|----------------------------------|-----|--------------------------------------|
| vb_code_test | CompletenessRepairEngine         | 408 | GUI completeness repair              |
| vb_code_test | FaultRepairEngine                | 1204| Fault repair                         |
| vb_code_test | HybridRepairEngine               | 681 | Hybrid repair                        |
| vb_code_test | L6_Repair                        | 1292| Layer 6 repair                       |
| vb_code_test | L8_RepairRouter                  | 1300| Layer 8 repair router                |
| vb_code_test | AppGoldRepairLoopIntegrator      | 970 | Gold repair loop                     |
| vb_code_test | RepairDecisionEngine             | 1412| Repair decision engine               |
| vb_code_test | RepairPlan                       | 1413| Repair plan                          |
| vb_code_test | RepairReader                     | 1414| Repair reader                        |
| vb_code_test | RepairSchema                     | 1415| Repair schema                        |
| vb_code_test | RepairWriter                     | 1416| Repair writer                        |
| vb_code_test | UnitRepairConfig                 | 1593| Unit repair config                   |
| vb_code_test | UnitRepairPlanner                | 1594| Unit repair planner                  |
| vb_code_test | UnitRepairReader                 | 1595| Unit repair reader                   |
| vb_code_test | VirtualRepairPlanner             | 1645| Virtual repair planner               |
| vb_code_test | ZramRepairLog                    | 1675| ZRAM repair log                      |
| vb_code_test | ODEMRecovery                     | 1344| ODEM recovery                        |
| vb_code_test | RecoveryConsole                  | 1409| Recovery console                     |
| vb_code_test | VBStyleRecoveryAuditor20260506   | 1622| VBStyle recovery auditor             |

## TIER 3: C FIX ENGINE (Project_WayneCascadeFile lineage)

| File             | Count | Purpose                              |
|------------------|-------|--------------------------------------|
| fix_engine.c     | ~15   | Main fix engine (many backup copies) |
| fix.c            | ~20   | Fix utility                          |
| fix.h            | ~6    | Fix header                           |
| Lib_fix_engine.c | 3     | Lib version of fix engine            |
| Lib_fix.c        | 3     | Lib version of fix                   |

## TIER 4: CURRENT Dom_Common (what we just built)

| File              | Purpose                                       |
|-------------------|-----------------------------------------------|
| ClassErrors.py    | In-RAM error→fix with msearch/reason/loop     |
| ClassBCL.py       | BCL packet parser/writer                      |
| ClassRules.py     | Rule checking/editing                         |
| ClassGraph.py     | Reports v4 graph wrapper                      |
| ClassTest.py      | ClassTester wrapper                           |

## TIER 5: ERROR KNOWLEDGE IN MYSQL

| DB       | Table             | Rows  | Purpose                          |
|----------|-------------------|-------|----------------------------------|
| vb_shared| error_knowledge   | ~125  | Known errors + solutions         |
| vb_shared| learned_rules     | 10540 | Patterns + fix actions           |
| vb_shared| know_problems     | 218   | Known problems                   |
| vb_shared| know_solutions    | 336   | Known solutions                  |
| vb_shared| execution_log     | ~340  | Command execution log            |
| vb_shared| neural_brain_state| ~100  | Action×interrogative weights     |
| vb_shared| scoring_model     | 4     | Scoring expressions              |

## TIER 6: ERROR FIX TRAINER (training data + scaffolding)

| File                     | Purpose                              |
|--------------------------|--------------------------------------|
| ErrorFixTrainer.py       | Generates 280 lessons → SQLite       |
| ErrorFixTrainer.db       | 280 broken→fixed pairs (20 per type) |
| ai_fix_bridge.py         | Bridge: error text → fix suggestion  |
| coretotch_fix.c          | C SGD trainer (40→64→16 MLP)         |
| coretotch_fix (binary)   | Compiled trainer + infer mode        |
| ai_fix_data_gen.c        | Training data generator              |
| fix_training.json        | 85 episodes of 40D→16D training data |

