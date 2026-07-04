#[@GHOST]
#[@VBSTYLE]
#[@FILEID] main.py
#[@SUMMARY] Entry point for CoreTotch -> CoreML layout policy training pipeline
#[@CLASS] none
#[@METHOD] main
#[@AUTHOR] Cascade
#[@DATE] 2026-06-28
#[@SESSION] coreml_layout_push

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from CoreTotchBridge import CoreTotchBridge
from CoreMLLayoutConverter import CoreMLLayoutConverter
from CoreMLLayoutDataGenerator import CoreMLLayoutDataGenerator
from CoreMLLayoutTrainer import CoreMLLayoutTrainer
from CoreMLExpertRegistry import CoreMLExpertRegistry
from CoreMLMultiExpertTrainer import CoreMLMultiExpertTrainer
from CoreMLModelBank import CoreMLModelBank
from CoreMLHotCache import CoreMLHotCache
from CoreMLModelDB import CoreMLModelDB
from CoreMLBackpack import CoreMLBackpack
from CoreMLRouter import CoreMLRouter
from CoreMLOrchestrator import CoreMLOrchestrator
from CoreMLDistributed import CoreMLDistributed
from CoreMLPythonTrainer import CoreMLPythonTrainer
from CoreMLASTTrainer import CoreMLASTTrainer
from CoreMLCapabilityRouter import CoreMLCapabilityRouter
from CoreMLTrainingGenerator import CoreMLTrainingGenerator
from CoreMLASTTransformer import CoreMLASTTransformer
from CoreMLCurriculumTeacher import CoreMLCurriculumTeacher
from CoreMLGenerativeRules import CoreMLGenerativeRules
from CoreMLSharedRepresentation import CoreMLSharedRepresentation
from CoreMLExpertCoordinator import CoreMLExpertCoordinator
from CoreMLAdaptiveTeacher import CoreMLAdaptiveTeacher
from Config_CoreMLLayout import MAX_EPISODES, TRAINING_EPOCHS


def main():
    args = sys.argv[1:]
    if len(args) == 0:
        sys.stdout.write("CoreTotch -> CoreML Pipeline\n")
        sys.stdout.write("=" * 50 + "\n")
        sys.stdout.write("Usage: python3 main.py <command> [args]\n\n")
        sys.stdout.write("Commands:\n")
        sys.stdout.write("  pipeline    — Full: export PT -> gen data -> C train -> build CoreML\n")
        sys.stdout.write("  export_pt   — Export PyTorch .pt weights to raw binary\n")
        sys.stdout.write("  gen_data    — Generate synthetic training data\n")
        sys.stdout.write("  c_train     — Run C CoreTotch SGD training\n")
        sys.stdout.write("  build_ml    — Build CoreML .mlpackage from C-trained weights\n")
        sys.stdout.write("  convert     — Convert PyTorch .pt to CoreML (direct, no C)\n")
        sys.stdout.write("  verify      — Verify CoreML model\n")
        sys.stdout.write("  evaluate    — Run inference on trained model\n")
        sys.stdout.write("  train_all   — Train all expert modules (vscode, browser, etc)\n")
        sys.stdout.write("  train_one   — Train single expert: train_one <name> [episodes] [epochs]\n")
        sys.stdout.write("  deploy_exp  — Deploy expert to CoreML: deploy_exp <name>\n")
        sys.stdout.write("  list_exp    — List registered experts\n")
        sys.stdout.write("  bank_list   — List all versioned models in the bank\n")
        sys.stdout.write("  bank_route  — Route to expert: bank_route <domain>\n")
        sys.stdout.write("  bank_ensemble — Ensemble: bank_ensemble <expert1,expert2,...>\n")
        sys.stdout.write("  bank_prune  — Remove old versions: bank_prune [keep_n]\n")
        sys.stdout.write("  cache_acquire — Load expert into hot cache: cache_acquire <name> <weights_path>\n")
        sys.stdout.write("  cache_stats — Show hot cache stats (hits, misses, evictions, RAM)\n")
        sys.stdout.write("  cache_evict — Evict LRU expert from hot cache\n")
        sys.stdout.write("  cache_clear — Clear entire hot cache\n")
        sys.stdout.write("  cache_size  — Set max hot cache size: cache_size <n>\n")
        sys.stdout.write("  db_init     — Initialize SQLite model database\n")
        sys.stdout.write("  db_import   — Import all .weights.bin files into DB\n")
        sys.stdout.write("  db_list     — List all models in database\n")
        sys.stdout.write("  db_stats    — Show DB stats (models, routes, cache, size)\n")
        sys.stdout.write("  db_route    — Route domain to expert in DB: db_route <domain>\n")
        sys.stdout.write("  db_hot_load — Load expert into DB hot cache: db_hot_load <name>\n")
        sys.stdout.write("  db_hot_stats — Show DB hot cache stats\n")
        sys.stdout.write("  bp_pack     — Pack expert into .backpack: bp_pack <name> <weights_path> [domain]\n")
        sys.stdout.write("  bp_unpack   — Unpack .backpack to files: bp_unpack <path> [output_dir]\n")
        sys.stdout.write("  bp_inspect  — Inspect .backpack metadata: bp_inspect <path>\n")
        sys.stdout.write("  bp_list     — List all backpacks\n")
        sys.stdout.write("  bp_store    — Store backpack in DB: bp_store <path>\n")
        sys.stdout.write("  bp_load     — Load backpack from DB: bp_load <name> [version]\n")
        sys.stdout.write("  route_init  — Initialize routing tables in DB\n")
        sys.stdout.write("  route_seed  — Seed initial scores for all models\n")
        sys.stdout.write("  route_auto  — Auto-route: route_auto <task_text>\n")
        sys.stdout.write("  route_rank  — Rank models for domain: route_rank <domain>\n")
        sys.stdout.write("  route_score — Update model score: route_score <name> <success> [accuracy]\n")
        sys.stdout.write("  route_history — Show routing history\n")
        sys.stdout.write("  exec        — Full pipeline: exec <task_text>\n")
        sys.stdout.write("  exec_ensemble — Ensemble: exec_ensemble <task_text> <expert1,expert2,...>\n")
        sys.stdout.write("  sys_status  — Full system status (DB, router, cache, backpacks)\n")
        sys.stdout.write("  sys_pipeline — Show pipeline definition\n")
        sys.stdout.write("  dist_init   — Initialize distributed GPU tables\n")
        sys.stdout.write("  dist_gpu    — Register GPU node: dist_gpu <node_id> [vram_gb] [name]\n")
        sys.stdout.write("  dist_auto   — Auto-assign experts to GPUs\n")
        sys.stdout.write("  dist_route  — Route expert to GPU: dist_route <expert_name>\n")
        sys.stdout.write("  dist_activate — Activate expert on GPU: dist_activate <expert> <node>\n")
        sys.stdout.write("  dist_deactivate — Deactivate expert: dist_deactivate <expert> <node>\n")
        sys.stdout.write("  dist_status — Show all GPU nodes, VRAM, active experts\n")
        sys.stdout.write("  dist_rebalance — Rebalance experts across GPUs\n")
        sys.stdout.write("  py_train    — Train expert on real Python: py_train <domain> [epochs]\n")
        sys.stdout.write("  py_train_all — Train all 5 experts on real Python\n")
        sys.stdout.write("  py_features — Extract features from file: py_features <filepath>\n")
        sys.stdout.write("  py_experts  — List Python-trained experts\n")
        sys.stdout.write("  ast_train   — Train AST layer: ast_train <layer> <domain> [epochs]\n")
        sys.stdout.write("  ast_train_all — Train all 4 layers x 5 domains (20 experts)\n")
        sys.stdout.write("  ast_classify — Classify file: ast_classify <filepath>\n")
        sys.stdout.write("  ast_features — Show all 4 layer features: ast_features <filepath>\n")
        sys.stdout.write("  ast_layers  — List all AST-trained experts\n")
        sys.stdout.write("  cap_init    — Initialize capability router (7 capabilities, 30 experts)\n")
        sys.stdout.write("  cap_route   — Route task to capabilities: cap_route <task_text>\n")
        sys.stdout.write("  cap_activate — Activate capability: cap_activate <capability_id>\n")
        sys.stdout.write("  cap_deactivate — Deactivate capability: cap_deactivate <capability_id>\n")
        sys.stdout.write("  cap_status  — Show all capabilities, active experts, RAM\n")
        sys.stdout.write("  cap_list    — List all capabilities with expert groups\n")
        sys.stdout.write("  gen_all     — Generate training data for all 7 layers\n")
        sys.stdout.write("  gen_train   — Train one layer: gen_train <layer> <domain> [epochs] [samples]\n")
        sys.stdout.write("  gen_train_all — Train all 7 layers x 5 domains (35 experts) on generated data\n")
        sys.stdout.write("  tf_list     — List all 10 AST transformations\n")
        sys.stdout.write("  tf_apply    — Apply transformation: tf_apply <domain> <transform_id>\n")
        sys.stdout.write("  tf_train    — Train transform expert: tf_train <domain> [epochs] [samples]\n")
        sys.stdout.write("  tf_train_all — Train all 10 transform + 5 invariant experts\n")
        sys.stdout.write("  tf_classify — Classify transformation: tf_classify <domain> <transform_id>\n")
        sys.stdout.write("  cur_list    — List all 7 curriculum teachers\n")
        sys.stdout.write("  cur_lesson  — Run one lesson: cur_lesson <teacher_id> [difficulty]\n")
        sys.stdout.write("  cur_run     — Run full curriculum: cur_run [lessons_per_level] [max_difficulty]\n")
        sys.stdout.write("  cur_train   — Train with curriculum: cur_train <teacher_id> <domain> [epochs]\n")
        sys.stdout.write("  cur_progress — Show learning progress across all teachers\n")
        sys.stdout.write("  rule_list   — List all 15 generative rules with prerequisites\n")
        sys.stdout.write("  rule_prereq — Show prerequisite chain: rule_prereq <rule_id>\n")
        sys.stdout.write("  rule_lesson — Run one rule lesson: rule_lesson <rule_id>\n")
        sys.stdout.write("  rule_run    — Run rule curriculum: rule_run [lessons_per_rule]\n")
        sys.stdout.write("  rule_train  — Train one rule: rule_train <rule_id> <domain> [epochs]\n")
        sys.stdout.write("  rule_train_all — Train all rules (respects prerequisites)\n")
        sys.stdout.write("  rule_mastery — Show mastery scores for all rules\n")
        sys.stdout.write("  sr_align    — Discover and register all experts in shared representation\n")
        sys.stdout.write("  sr_list     — List all experts with type, domain, shared semantic mapping\n")
        sys.stdout.write("  sr_encode   — Encode expert output to shared semantic space\n")
        sys.stdout.write("  sr_space    — Run feature through ALL experts, show ensemble semantic space\n")
        sys.stdout.write("  coord_list  — List all task types and fusion strategies\n")
        sys.stdout.write("  coord_route — Route a task: coord_route <task_description>\n")
        sys.stdout.write("  coord_pipeline — Show coordination pipeline: coord_pipeline <task_description>\n")
        sys.stdout.write("  coord_run   — Full coordination: coord_run <task_description> <feature_json_file>\n")
        sys.stdout.write("  coord_log   — Show recent coordination events\n")
        sys.stdout.write("  ad_teach    — Teach rule with adaptive retries: ad_teach <rule_id> <domain>\n")
        sys.stdout.write("  ad_teach_all — Teach all rules adaptively (prerequisite-gated, auto-retry)\n")
        sys.stdout.write("  ad_diagnose — Diagnose rule failures by question type: ad_diagnose <rule_id> <domain>\n")
        sys.stdout.write("  ad_progress — Show adaptive mastery + retry history\n")
        sys.stdout.write("\nExamples:\n")
        sys.stdout.write("  python3 main.py pipeline 200 50\n")
        sys.stdout.write("  python3 main.py c_train 50 0.001\n")
        sys.stdout.flush()
        return

    command = args[0]
    bridge = CoreTotchBridge()

    if command == "pipeline":
        episodes = int(args[1]) if len(args) > 1 else MAX_EPISODES
        epochs = int(args[2]) if len(args) > 2 else TRAINING_EPOCHS
        lr = float(args[3]) if len(args) > 3 else 0.001
        ok, data, err = bridge.Run("full_pipeline", {
            "episodes": episodes,
            "epochs": epochs,
            "lr": lr,
        })
        if ok:
            sys.stdout.write("\n" + "=" * 50 + "\n")
            sys.stdout.write("PIPELINE COMPLETE\n")
            sys.stdout.write("=" * 50 + "\n")
            sys.stdout.write(str(data) + "\n")
        else:
            sys.stdout.write("\nPIPELINE FAILED: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "export_pt":
        ok, data, err = bridge.Run("export_pt_to_bin", {})
        if ok:
            sys.stdout.write("Export OK: " + str(data) + "\n")
        else:
            sys.stdout.write("Export FAIL: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "gen_data":
        episodes = int(args[1]) if len(args) > 1 else MAX_EPISODES
        gen = CoreMLLayoutDataGenerator()
        ok, data, err = gen.Run("generate", {"episodes": episodes})
        if ok:
            sys.stdout.write("Generate OK: " + str(data) + "\n")
            ok2, saveData, saveErr = gen.Run("save", {})
            if ok2:
                sys.stdout.write("Save OK: " + str(saveData) + "\n")
        else:
            sys.stdout.write("Generate FAIL: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "c_train":
        epochs = int(args[1]) if len(args) > 1 else TRAINING_EPOCHS
        lr = float(args[2]) if len(args) > 2 else 0.001
        ok, data, err = bridge.Run("train_c", {"epochs": epochs, "lr": lr})
        if ok:
            sys.stdout.write("C Train OK: " + str(data) + "\n")
        else:
            sys.stdout.write("C Train FAIL: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "build_ml":
        ok, data, err = bridge.Run("build_coreml", {})
        if ok:
            sys.stdout.write("Build CoreML OK: " + str(data) + "\n")
        else:
            sys.stdout.write("Build CoreML FAIL: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "convert":
        converter = CoreMLLayoutConverter()
        ok, data, err = converter.Run("convert", {})
        if ok:
            sys.stdout.write("Convert OK: " + str(data) + "\n")
        else:
            sys.stdout.write("Convert FAIL: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "verify":
        converter = CoreMLLayoutConverter()
        ok, data, err = converter.Run("verify", {})
        if ok:
            sys.stdout.write("Verify OK: " + str(data) + "\n")
        else:
            sys.stdout.write("Verify FAIL: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "evaluate":
        trainer = CoreMLLayoutTrainer()
        ok, data, err = trainer.Run("evaluate", {})
        if ok:
            sys.stdout.write("Evaluate OK: " + str(data) + "\n")
        else:
            sys.stdout.write("Evaluate FAIL: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "train_all":
        episodes = int(args[1]) if len(args) > 1 else 100
        epochs = int(args[2]) if len(args) > 2 else 30
        lr = float(args[3]) if len(args) > 3 else 0.001
        trainer = CoreMLMultiExpertTrainer()
        ok, data, err = trainer.Run("train_all", {"episodes": episodes, "epochs": epochs, "lr": lr})
        if ok:
            sys.stdout.write("\nAll experts trained: " + str(data) + "\n")
        else:
            sys.stdout.write("\nExpert training failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "train_one":
        name = args[1] if len(args) > 1 else "vscode"
        episodes = int(args[2]) if len(args) > 2 else 100
        epochs = int(args[3]) if len(args) > 3 else 30
        trainer = CoreMLMultiExpertTrainer()
        ok, data, err = trainer.Run("train_one", {"name": name, "episodes": episodes, "epochs": epochs})
        if ok:
            sys.stdout.write("Expert trained: " + str(data) + "\n")
        else:
            sys.stdout.write("Expert failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "deploy_exp":
        name = args[1] if len(args) > 1 else "vscode"
        trainer = CoreMLMultiExpertTrainer()
        ok, data, err = trainer.Run("deploy", {"name": name})
        if ok:
            sys.stdout.write("Expert deployed: " + str(data) + "\n")
        else:
            sys.stdout.write("Deploy failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "list_exp":
        registry = CoreMLExpertRegistry()
        ok, data, err = registry.Run("list", {})
        if ok:
            sys.stdout.write("Experts: " + str(data) + "\n")
        else:
            sys.stdout.write("List failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "bank_list":
        bank = CoreMLModelBank()
        ok, data, err = bank.Run("list_versions", {})
        if ok:
            sys.stdout.write("Model Bank:\n")
            for m in data.get("models", []):
                sys.stdout.write("  " + m["name"] + " (" + m["domain"] + "): " + str(len(m["versions"])) + " versions\n")
            sys.stdout.write("Total: " + str(data["total_models"]) + " models, " + str(data["total_versions"]) + " versions\n")
        else:
            sys.stdout.write("Bank list failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "bank_route":
        domain = args[1] if len(args) > 1 else "vscode"
        bank = CoreMLModelBank()
        ok, data, err = bank.Run("route", {"domain": domain})
        if ok:
            sys.stdout.write("Routed to: " + data["expert"] + " v" + str(data["version"]) + "\n")
            sys.stdout.write("  RAM: " + data["ram_usage"] + "\n")
        else:
            sys.stdout.write("Route failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "bank_ensemble":
        names = args[1].split(",") if len(args) > 1 else ["vscode", "browser"]
        bank = CoreMLModelBank()
        ok, data, err = bank.Run("ensemble", {"experts": names})
        if ok:
            sys.stdout.write("Ensemble created: " + str(len(data["ensemble"])) + " experts\n")
            sys.stdout.write("  RAM: " + data["ram_usage"] + "\n")
            for e in data["ensemble"]:
                sys.stdout.write("  " + e["name"] + " v" + str(e["version"]) + " weight=" + str(round(e["weight"], 3)) + "\n")
        else:
            sys.stdout.write("Ensemble failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "bank_prune":
        keepN = int(args[1]) if len(args) > 1 else 2
        bank = CoreMLModelBank()
        ok, data, err = bank.Run("prune", {"keep": keepN})
        if ok:
            sys.stdout.write("Pruned: " + str(data["pruned"]) + " old versions, kept " + str(data["kept_per_model"]) + " per model\n")
        else:
            sys.stdout.write("Prune failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "cache_acquire":
        name = args[1] if len(args) > 1 else "vscode"
        weightsPath = args[2] if len(args) > 2 else ""
        if not weightsPath:
            weightsPath = os.path.join("experts", name + ".weights.bin")
        cache = CoreMLHotCache()
        ok, data, err = cache.Run("acquire", {"name": name, "weights_path": weightsPath})
        if ok:
            sys.stdout.write("Cache " + data["status"] + ": " + data["name"] + " (" + data["state"] + ")\n")
        else:
            sys.stdout.write("Cache acquire failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "cache_stats":
        cache = CoreMLHotCache()
        ok, data, err = cache.Run("stats", {})
        if ok:
            sys.stdout.write("Hot Cache Stats:\n")
            sys.stdout.write("  Hits: " + str(data["stats"]["hits"]) + "\n")
            sys.stdout.write("  Misses: " + str(data["stats"]["misses"]) + "\n")
            sys.stdout.write("  Evictions: " + str(data["stats"]["evictions"]) + "\n")
            sys.stdout.write("  Hit rate: " + str(data["hit_rate"]) + "\n")
            sys.stdout.write("  Hot models: " + str(data["hot_count"]) + "/" + str(data["max_hot"]) + "\n")
            sys.stdout.write("  RAM used: " + str(data["ram_used_kb"]) + " KB\n")
            for m in data["hot_models"]:
                sys.stdout.write("    " + m["name"] + " (accesses=" + str(m["access_count"]) + ")\n")
        else:
            sys.stdout.write("Stats failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "cache_evict":
        cache = CoreMLHotCache()
        ok, data, err = cache.Run("evict", {"count": 1})
        if ok:
            sys.stdout.write("Evicted: " + str(data["evicted"]) + " (freed " + str(data["freed_bytes"]) + " bytes)\n")
        else:
            sys.stdout.write("Evict failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "cache_clear":
        cache = CoreMLHotCache()
        ok, data, err = cache.Run("clear", {})
        if ok:
            sys.stdout.write("Cleared " + str(data["cleared"]) + " models (freed " + str(data["freed_bytes"]) + " bytes)\n")
        else:
            sys.stdout.write("Clear failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "cache_size":
        newSize = int(args[1]) if len(args) > 1 else 2
        cache = CoreMLHotCache()
        ok, data, err = cache.Run("set_cache_size", {"size": newSize})
        if ok:
            sys.stdout.write("Cache size set to " + str(data["max_hot"]) + " (current: " + str(data["current_cache"]) + ")\n")
        else:
            sys.stdout.write("Set size failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "db_init":
        db = CoreMLModelDB()
        ok, data, err = db.Run("init", {})
        if ok:
            sys.stdout.write("DB initialized: " + str(data) + "\n")
        else:
            sys.stdout.write("DB init failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "db_import":
        db = CoreMLModelDB()
        ok, data, err = db.Run("import_files", {})
        if ok:
            sys.stdout.write("Imported: " + str(data["imported"]) + " models, skipped: " + str(data["skipped"]) + "\n")
        else:
            sys.stdout.write("Import failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "db_list":
        db = CoreMLModelDB()
        ok, data, err = db.Run("list", {})
        if ok:
            sys.stdout.write("Model Database (" + str(data["total_models"]) + " models):\n")
            for m in data["models"]:
                active = "*" if m["active"] else " "
                sys.stdout.write("  " + active + " " + m["name"] + " v" + str(m["version"]) + " (" + m["domain"] + ")\n")
        else:
            sys.stdout.write("DB list failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "db_stats":
        db = CoreMLModelDB()
        ok, data, err = db.Run("stats", {})
        if ok:
            sys.stdout.write("Database Stats:\n")
            sys.stdout.write("  Models: " + str(data["total_models"]) + "\n")
            sys.stdout.write("  Routes: " + str(data["total_routes"]) + "\n")
            sys.stdout.write("  Hot cache: " + str(data["hot_cache_slots"]) + "/" + str(data["max_hot"]) + "\n")
            sys.stdout.write("  DB size: " + str(data["db_size_kb"]) + " KB\n")
            sys.stdout.write("  Counters: " + str(data["counters"]) + "\n")
        else:
            sys.stdout.write("DB stats failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "db_route":
        domain = args[1] if len(args) > 1 else "vscode"
        db = CoreMLModelDB()
        ok, data, err = db.Run("route", {"domain": domain})
        if ok:
            sys.stdout.write("Routed: " + domain + " -> " + data["expert"] + " v" + str(data["version"]) + "\n")
        else:
            sys.stdout.write("Route failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "db_hot_load":
        name = args[1] if len(args) > 1 else "vscode"
        db = CoreMLModelDB()
        ok, data, err = db.Run("hot_load", {"name": name})
        if ok:
            sys.stdout.write("Cache " + data["status"] + ": " + data["name"] + " slot=" + str(data["slot"]) + "\n")
        else:
            sys.stdout.write("Hot load failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "db_hot_stats":
        db = CoreMLModelDB()
        ok, data, err = db.Run("hot_stats", {})
        if ok:
            sys.stdout.write("DB Hot Cache:\n")
            sys.stdout.write("  Hot: " + str(data["hot_count"]) + "/" + str(data["max_hot"]) + "\n")
            sys.stdout.write("  RAM: " + str(data["ram_kb"]) + " KB\n")
            sys.stdout.write("  Hit rate: " + str(data["hit_rate"]) + "\n")
            sys.stdout.write("  Counters: " + str(data["counters"]) + "\n")
            for m in data["hot_models"]:
                sys.stdout.write("    slot " + str(m["slot"]) + ": " + m["name"] + " (accesses=" + str(m["access_count"]) + ")\n")
        else:
            sys.stdout.write("Hot stats failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "bp_pack":
        name = args[1] if len(args) > 1 else "vscode"
        weightsPath = args[2] if len(args) > 2 else os.path.join("experts", name + ".weights.bin")
        domain = args[3] if len(args) > 3 else name
        bp = CoreMLBackpack()
        ok, data, err = bp.Run("pack", {"name": name, "weights_path": weightsPath, "domain": domain, "description": domain + " layout expert"})
        if ok:
            sys.stdout.write("Packed: " + data["packed"] + " (" + str(data["total_kb"]) + " KB)\n")
        else:
            sys.stdout.write("Pack failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "bp_unpack":
        path = args[1] if len(args) > 1 else ""
        outputDir = args[2] if len(args) > 2 else "backpacks/unpacked"
        bp = CoreMLBackpack()
        ok, data, err = bp.Run("unpack", {"path": path, "output_dir": outputDir})
        if ok:
            sys.stdout.write("Unpacked: " + data["unpacked"] + " v" + str(data["metadata"]["version"]) + "\n")
        else:
            sys.stdout.write("Unpack failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "bp_inspect":
        path = args[1] if len(args) > 1 else ""
        bp = CoreMLBackpack()
        ok, data, err = bp.Run("inspect", {"path": path})
        if ok:
            sys.stdout.write("Backpack: " + data["metadata"]["name"] + "\n")
            sys.stdout.write("  Domain: " + data["metadata"]["domain"] + "\n")
            sys.stdout.write("  Version: " + str(data["metadata"]["version"]) + "\n")
            sys.stdout.write("  Size: " + str(data["file_size_kb"]) + " KB\n")
            sys.stdout.write("  Weights: " + str(data["weights_params"]) + " params (" + str(data["weights_bytes"]) + " bytes)\n")
            sys.stdout.write("  Architecture: " + str(data["metadata"]["architecture"]["layers"]) + "\n")
        else:
            sys.stdout.write("Inspect failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "bp_list":
        bp = CoreMLBackpack()
        ok, data, err = bp.Run("list_backpacks", {})
        if ok:
            sys.stdout.write("Backpacks (" + str(data["total"]) + "):\n")
            for b in data["backpacks"]:
                sys.stdout.write("  " + b["name"] + " v" + str(b["version"]) + " (" + b["domain"] + ") " + str(b["size_kb"]) + " KB\n")
        else:
            sys.stdout.write("List failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "bp_store":
        path = args[1] if len(args) > 1 else ""
        bp = CoreMLBackpack()
        ok, data, err = bp.Run("store_in_db", {"path": path})
        if ok:
            sys.stdout.write("Stored in DB: " + data["stored"] + " v" + str(data["version"]) + " (" + str(data["total_backpacks_in_db"]) + " total)\n")
        else:
            sys.stdout.write("Store failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command == "bp_load":
        name = args[1] if len(args) > 1 else "vscode"
        version = args[2] if len(args) > 2 else "latest"
        bp = CoreMLBackpack()
        ok, data, err = bp.Run("load_from_db", {"name": name, "version": version})
        if ok:
            sys.stdout.write("Loaded from DB: " + data["loaded"] + " v" + str(data["version"]) + " -> " + data["path"] + "\n")
        else:
            sys.stdout.write("Load failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command in ("route_init", "route_seed", "route_auto", "route_rank", "route_score", "route_history"):
        router = CoreMLRouter()
        if command == "route_init":
            ok, data, err = router.Run("init", {})
            if ok:
                sys.stdout.write("Router initialized: " + str(data) + "\n")
            else:
                sys.stdout.write("Init failed: " + str(err) + "\n")
        elif command == "route_seed":
            ok, data, err = router.Run("seed_scores", {})
            if ok:
                sys.stdout.write("Seeded " + str(data["seeded"]) + " model scores\n")
            else:
                sys.stdout.write("Seed failed: " + str(err) + "\n")
        elif command == "route_auto":
            taskText = " ".join(args[1:]) if len(args) > 1 else "ide editor code panel"
            ok, data, err = router.Run("auto_route", {"task_input": taskText})
            if ok:
                sys.stdout.write("Auto-routed:\n")
                sys.stdout.write("  Task: " + data["task_input"] + "\n")
                sys.stdout.write("  Domain: " + data["detected_domain"] + " (confidence: " + str(data["detection_confidence"]) + ")\n")
                sys.stdout.write("  Model: " + data["selected_model"] + " v" + str(data["selected_version"]) + "\n")
                sys.stdout.write("  Score: " + str(data["score"]) + "\n")
                sys.stdout.write("  RAM: " + str(data["ram_kb"]) + " KB\n")
            else:
                sys.stdout.write("Auto-route failed: " + str(err) + "\n")
        elif command == "route_rank":
            domain = args[1] if len(args) > 1 else "vscode"
            ok, data, err = router.Run("rank", {"domain": domain})
            if ok:
                sys.stdout.write("Rankings for " + domain + ":\n")
                for r in data["rankings"]:
                    sys.stdout.write("  #" + str(r["rank"]) + " " + r["model"] + " v" + str(r["version"]) + " score=" + str(r["score"]) + " acc=" + str(r["accuracy"]) + " usage=" + str(r["usage_count"]) + "\n")
            else:
                sys.stdout.write("Rank failed: " + str(err) + "\n")
        elif command == "route_score":
            name = args[1] if len(args) > 1 else "vscode"
            success = args[2].lower() != "false" if len(args) > 2 else True
            accuracy = float(args[3]) if len(args) > 3 else None
            ok, data, err = router.Run("update_score", {"model_name": name, "success": success, "accuracy": accuracy})
            if ok:
                sys.stdout.write("Score updated: " + data["model"] + " -> " + str(data["new_score"]) + " (success_rate=" + str(data["success_rate"]) + ")\n")
            else:
                sys.stdout.write("Score failed: " + str(err) + "\n")
        elif command == "route_history":
            ok, data, err = router.Run("history", {"limit": 10})
            if ok:
                sys.stdout.write("Routing History:\n")
                for h in data["history"]:
                    sys.stdout.write("  " + h["model"] + " v" + str(h["version"]) + " (" + h["domain"] + ") score=" + str(h["score"]) + "\n")
            else:
                sys.stdout.write("History failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command in ("exec", "exec_ensemble", "sys_status", "sys_pipeline"):
        orch = CoreMLOrchestrator()
        if command == "exec":
            taskText = " ".join(args[1:]) if len(args) > 1 else "ide editor code panel"
            ok, data, err = orch.Run("execute", {"task_input": taskText})
            if ok:
                sys.stdout.write("=== EXECUTION COMPLETE ===\n")
                sys.stdout.write("Task: " + data["task_input"] + "\n")
                sys.stdout.write("Domain: " + data["domain"] + "\n")
                sys.stdout.write("Model: " + data["model"] + " v" + str(data["version"]) + "\n")
                sys.stdout.write("Inference: " + str(data["inference_ms"]) + " ms\n")
                sys.stdout.write("Total: " + str(data["total_ms"]) + " ms\n")
                sys.stdout.write("RAM: " + str(data["ram_kb"]) + " KB\n")
                sys.stdout.write("Success: " + str(data["success"]) + "\n")
                if data.get("c_output"):
                    sys.stdout.write("C output: " + data["c_output"][:100] + "\n")
                sys.stdout.write("Pipeline steps:\n")
                for step in data["pipeline"]:
                    sys.stdout.write("  " + str(step["step"]) + ". " + step["name"] + " (" + str(step.get("time_ms", 0)) + " ms)\n")
            else:
                sys.stdout.write("Execute failed: " + str(err) + "\n")
        elif command == "exec_ensemble":
            taskText = args[1] if len(args) > 1 else "ide editor code"
            expertList = args[2].split(",") if len(args) > 2 else ["vscode", "browser"]
            ok, data, err = orch.Run("execute_ensemble", {"task_input": taskText, "experts": expertList})
            if ok:
                sys.stdout.write("=== ENSEMBLE EXECUTION ===\n")
                sys.stdout.write("Task: " + data["task_input"] + "\n")
                sys.stdout.write("Experts: " + str(data["experts_loaded"]) + " loaded\n")
                sys.stdout.write("RAM: " + str(data["ram_kb"]) + " KB\n")
                sys.stdout.write("Total: " + str(data["total_ms"]) + " ms\n")
                if data.get("c_output"):
                    sys.stdout.write("C output: " + data["c_output"][:100] + "\n")
            else:
                sys.stdout.write("Ensemble failed: " + str(err) + "\n")
        elif command == "sys_status":
            ok, data, err = orch.Run("status", {})
            if ok:
                sys.stdout.write("=== AI RUNTIME OS STATUS ===\n")
                db = data.get("database", {})
                rt = data.get("router", {})
                bp = data.get("backpacks", {})
                ct = data.get("coretotch", {})
                sys.stdout.write("Database:\n")
                sys.stdout.write("  Models: " + str(db.get("models", 0)) + "\n")
                sys.stdout.write("  Routes: " + str(db.get("routes", 0)) + "\n")
                sys.stdout.write("  Size: " + str(db.get("db_size_kb", 0)) + " KB\n")
                sys.stdout.write("  Counters: " + str(db.get("counters", {})) + "\n")
                sys.stdout.write("Router/Cache:\n")
                sys.stdout.write("  Hot: " + str(rt.get("hot_models", 0)) + "/" + str(rt.get("max_hot", 0)) + "\n")
                sys.stdout.write("  RAM: " + str(rt.get("ram_kb", 0)) + " KB\n")
                sys.stdout.write("  Hit rate: " + str(rt.get("hit_rate", 0)) + "\n")
                sys.stdout.write("Backpacks: " + str(bp.get("total", 0)) + "\n")
                sys.stdout.write("CoreTotch: " + ("OK" if ct.get("exists") else "MISSING") + "\n")
            else:
                sys.stdout.write("Status failed: " + str(err) + "\n")
        elif command == "sys_pipeline":
            ok, data, err = orch.Run("pipeline", {})
            if ok:
                sys.stdout.write("=== AI RUNTIME OS PIPELINE ===\n")
                for step in data["pipeline"]:
                    sys.stdout.write("  " + str(step["step"]) + ". " + step["name"] + " [" + step["component"] + "] " + step["input"] + " -> " + step["output"] + "\n")
                sys.stdout.write("\nComponents:\n")
                for comp in data["components"]:
                    sys.stdout.write("  " + comp["name"] + ": " + comp["role"] + "\n")
                contract = data["interface_contract"]
                sys.stdout.write("\nInterface Contract:\n")
                sys.stdout.write("  Architecture: " + contract["layers"] + "\n")
                sys.stdout.write("  Params: " + str(contract["weight_params"]) + " (" + str(contract["weight_bytes"]) + " bytes)\n")
                sys.stdout.write("  Backpack: " + contract["backpack_size"] + "\n")
                sys.stdout.write("  RAM per expert: " + contract["ram_per_expert"] + "\n")
            else:
                sys.stdout.write("Pipeline failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command in ("dist_init", "dist_gpu", "dist_auto", "dist_route", "dist_activate", "dist_deactivate", "dist_status", "dist_rebalance"):
        dist = CoreMLDistributed()
        if command == "dist_init":
            ok, data, err = dist.Run("init", {})
            if ok:
                sys.stdout.write("Distributed initialized: " + str(data) + "\n")
            else:
                sys.stdout.write("Init failed: " + str(err) + "\n")
        elif command == "dist_gpu":
            nodeId = args[1] if len(args) > 1 else "gpu0"
            vramGb = float(args[2]) if len(args) > 2 else 8.0
            name = args[3] if len(args) > 3 else nodeId
            ok, data, err = dist.Run("register_gpu", {"node_id": nodeId, "vram_kb": vramGb * 1024 * 1024, "name": name})
            if ok:
                sys.stdout.write("GPU registered: " + data["registered"] + " (" + str(data["vram_total_gb"]) + " GB VRAM, " + str(data["experts assignable"]) + " experts max)\n")
            else:
                sys.stdout.write("GPU register failed: " + str(err) + "\n")
        elif command == "dist_auto":
            ok, data, err = dist.Run("auto_assign", {})
            if ok:
                sys.stdout.write("Auto-assigned " + str(data["auto_assigned"]) + " experts across " + str(data["gpu_nodes"]) + " GPUs\n")
            else:
                sys.stdout.write("Auto-assign failed: " + str(err) + "\n")
        elif command == "dist_route":
            expertName = args[1] if len(args) > 1 else "vscode"
            ok, data, err = dist.Run("route_distributed", {"expert_name": expertName})
            if ok:
                sys.stdout.write("Routed: " + data["expert"] + " -> " + data["node"] + " [" + data["state"] + "] " + data["action"] + "\n")
            else:
                sys.stdout.write("Route failed: " + str(err) + "\n")
        elif command == "dist_activate":
            expertName = args[1] if len(args) > 1 else "vscode"
            nodeId = args[2] if len(args) > 2 else "gpu0"
            ok, data, err = dist.Run("activate", {"expert_name": expertName, "node_id": nodeId})
            if ok:
                sys.stdout.write("Activated: " + data["expert"] + " on " + data["node"] + " (" + str(data.get("ram_kb", 0)) + " KB VRAM)\n")
            else:
                sys.stdout.write("Activate failed: " + str(err) + "\n")
        elif command == "dist_deactivate":
            expertName = args[1] if len(args) > 1 else "vscode"
            nodeId = args[2] if len(args) > 2 else "gpu0"
            ok, data, err = dist.Run("deactivate", {"expert_name": expertName, "node_id": nodeId})
            if ok:
                sys.stdout.write("Deactivated: " + data["expert"] + " on " + data["node"] + " (freed " + str(data.get("freed_kb", 0)) + " KB)\n")
            else:
                sys.stdout.write("Deactivate failed: " + str(err) + "\n")
        elif command == "dist_status":
            ok, data, err = dist.Run("status", {})
            if ok:
                sys.stdout.write("=== DISTRIBUTED GPU STATUS ===\n")
                sys.stdout.write("GPUs: " + str(data["total_gpus"]) + " | Total VRAM: " + str(data["total_vram_gb"]) + " GB\n")
                sys.stdout.write("Active: " + data["sparse_ratio"] + " experts\n\n")
                for g in data["gpu_nodes"]:
                    sys.stdout.write("  " + g["node_id"] + " (" + g["name"] + ")\n")
                    sys.stdout.write("    VRAM: " + str(g["vram_total_gb"]) + " GB | Used: " + str(g["vram_used_kb"]) + " KB | Free: " + str(g["vram_free_kb"]) + " KB\n")
                    sys.stdout.write("    Utilization: " + str(g["utilization_pct"]) + "% | Status: " + g["status"] + "\n")
                    sys.stdout.write("    Experts: " + str(g["active_experts"]) + " active / " + str(g["assigned_experts"]) + " assigned\n")
            else:
                sys.stdout.write("Status failed: " + str(err) + "\n")
        elif command == "dist_rebalance":
            ok, data, err = dist.Run("rebalance", {})
            if ok:
                sys.stdout.write("Rebalanced: " + str(data["redistributed"]) + " experts across " + str(data["gpu_nodes"]) + " GPUs (all deactivated first)\n")
            else:
                sys.stdout.write("Rebalance failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command in ("py_train", "py_train_all", "py_features", "py_experts"):
        ptrainer = CoreMLPythonTrainer()
        if command == "py_train":
            domain = args[1] if len(args) > 1 else "vscode"
            epochs = int(args[2]) if len(args) > 2 else 300
            sys.stdout.write("Training " + domain + " on real Python code (" + str(epochs) + " epochs)...\n")
            sys.stdout.flush()
            ok, data, err = ptrainer.Run("train_expert", {"domain": domain, "epochs": epochs})
            if ok:
                sys.stdout.write("Trained: " + data["domain"] + "\n")
                sys.stdout.write("  Samples: " + str(data["samples"]) + "\n")
                sys.stdout.write("  Epochs: " + str(data["epochs"]) + "\n")
                sys.stdout.write("  " + data["first_loss"] + "\n")
                sys.stdout.write("  " + data["last_loss"] + "\n")
                sys.stdout.write("  Weights: " + data["output_weights"] + "\n")
                sys.stdout.write("  Success: " + str(data["success"]) + "\n")
            else:
                sys.stdout.write("Train failed: " + str(err) + "\n")
        elif command == "py_train_all":
            epochs = int(args[1]) if len(args) > 1 else 300
            sys.stdout.write("Training ALL experts on real Python code (" + str(epochs) + " epochs each)...\n")
            sys.stdout.flush()
            ok, data, err = ptrainer.Run("train_all", {"epochs": epochs})
            if ok:
                sys.stdout.write("Trained " + str(data["trained"]) + "/" + str(data["total"]) + " experts:\n")
                for r in data["results"]:
                    status = "OK" if r.get("success") else "FAIL"
                    sys.stdout.write("  " + r["domain"] + ": " + status + " | " + r.get("first_loss", "") + " -> " + r.get("last_loss", "") + "\n")
            else:
                sys.stdout.write("Train all failed: " + str(err) + "\n")
        elif command == "py_features":
            filepath = args[1] if len(args) > 1 else "Dom_CoreML_Layout/main.py"
            ok, data, err = ptrainer.Run("extract_features", {"filepath": filepath})
            if ok:
                sys.stdout.write("File: " + data["filepath"] + "\n")
                sys.stdout.write("Features (" + str(data["feature_count"]) + "D):\n")
                for i, v in enumerate(data["features"]):
                    sys.stdout.write("  [" + str(i) + "] " + str(round(v, 4)) + "\n")
            else:
                sys.stdout.write("Extract failed: " + str(err) + "\n")
        elif command == "py_experts":
            ok, data, err = ptrainer.Run("list_experts", {})
            if ok:
                sys.stdout.write("Python-trained experts (" + str(data["total"]) + "):\n")
                for e in data["experts"]:
                    sys.stdout.write("  " + e["name"] + " (" + str(e["size_kb"]) + " KB)\n")
            else:
                sys.stdout.write("List failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command in ("ast_train", "ast_train_all", "ast_classify", "ast_features", "ast_layers"):
        astTrainer = CoreMLASTTrainer()
        if command == "ast_train":
            layer = args[1] if len(args) > 1 else "grammar"
            domain = args[2] if len(args) > 2 else "vscode"
            epochs = int(args[3]) if len(args) > 3 else 300
            sys.stdout.write("Training AST layer '" + layer + "' for domain '" + domain + "' (" + str(epochs) + " epochs)...\n")
            sys.stdout.flush()
            ok, data, err = astTrainer.Run("train_layer", {"layer": layer, "domain": domain, "epochs": epochs})
            if ok:
                sys.stdout.write("Trained: " + data["layer"] + "/" + data["domain"] + "\n")
                sys.stdout.write("  Samples: " + str(data["samples"]) + "\n")
                sys.stdout.write("  " + data["first_loss"] + "\n")
                sys.stdout.write("  " + data["last_loss"] + "\n")
                sys.stdout.write("  Weights: " + data["output_weights"] + "\n")
            else:
                sys.stdout.write("Train failed: " + str(err) + "\n")
        elif command == "ast_train_all":
            epochs = int(args[1]) if len(args) > 1 else 300
            sys.stdout.write("Training ALL AST layers (4 layers x 5 domains = 20 experts)...\n")
            sys.stdout.flush()
            ok, data, err = astTrainer.Run("train_all_layers", {"epochs": epochs})
            if ok:
                sys.stdout.write("Trained " + str(data["trained"]) + "/" + str(data["total"]) + " AST experts:\n")
                for r in data["results"]:
                    status = "OK" if r.get("success") else "FAIL"
                    sys.stdout.write("  " + r["layer"] + "/" + r["domain"] + ": " + status + " | " + r.get("first_loss", "") + " -> " + r.get("last_loss", "") + "\n")
            else:
                sys.stdout.write("Train all failed: " + str(err) + "\n")
        elif command == "ast_classify":
            filepath = args[1] if len(args) > 1 else "Dom_CoreML_Layout/main.py"
            ok, data, err = astTrainer.Run("classify", {"filepath": filepath})
            if ok:
                sys.stdout.write("=== AST CLASSIFICATION ===\n")
                sys.stdout.write("File: " + data["filepath"] + "\n")
                sys.stdout.write("Final: " + data["final_classification"] + "\n")
                sys.stdout.write("Votes: " + str(data["vote_counts"]) + "\n")
                for layer, vote in data["layer_votes"].items():
                    sys.stdout.write("  " + layer + " -> " + vote["winner"] + " (scores: " + str({k: round(v, 4) for k, v in vote["scores"].items()}) + ")\n")
            else:
                sys.stdout.write("Classify failed: " + str(err) + "\n")
        elif command == "ast_features":
            filepath = args[1] if len(args) > 1 else "Dom_CoreML_Layout/main.py"
            ok, data, err = astTrainer.Run("extract_ast_features", {"filepath": filepath})
            if ok:
                sys.stdout.write("File: " + data["filepath"] + "\n")
                for layer, feats in data["layers"].items():
                    nonzero = sum(1 for v in feats if v > 0)
                    sys.stdout.write("  " + layer + " (" + str(nonzero) + " active features): ")
                    sys.stdout.write(" ".join(str(round(v, 2)) for v in feats[:10]) + "...\n")
            else:
                sys.stdout.write("Extract failed: " + str(err) + "\n")
        elif command == "ast_layers":
            ok, data, err = astTrainer.Run("list_layers", {})
            if ok:
                sys.stdout.write("AST-trained experts (" + str(data["total"]) + "):\n")
                for layer in data["layers"]:
                    experts = data["by_layer"].get(layer, [])
                    sys.stdout.write("  " + layer + " (" + str(len(experts)) + " experts):\n")
                    for e in experts:
                        sys.stdout.write("    " + e["domain"] + " (" + str(e["size_kb"]) + " KB)\n")
            else:
                sys.stdout.write("List failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command in ("cap_init", "cap_route", "cap_activate", "cap_deactivate", "cap_status", "cap_list"):
        capRouter = CoreMLCapabilityRouter()
        if command == "cap_init":
            ok, data, err = capRouter.Run("init", {})
            if ok:
                sys.stdout.write("Capability router initialized:\n")
                sys.stdout.write("  Capabilities: " + str(data["capabilities"]) + "\n")
                sys.stdout.write("  Expert assignments: " + str(data["expert_assignments"]) + "\n")
                sys.stdout.write("  Keyword mappings: " + str(data["keyword_mappings"]) + "\n")
            else:
                sys.stdout.write("Init failed: " + str(err) + "\n")
        elif command == "cap_route":
            taskText = " ".join(args[1:]) if len(args) > 1 else "analyze python code structure"
            ok, data, err = capRouter.Run("route_task", {"task_input": taskText})
            if ok:
                sys.stdout.write("=== CAPABILITY ROUTING ===\n")
                sys.stdout.write("Task: " + data["task_input"] + "\n")
                sys.stdout.write("Routing: " + str(data["routing_ms"]) + " ms\n")
                sys.stdout.write("Detected capabilities:\n")
                for cap in data["detected_capabilities"]:
                    sys.stdout.write("  " + cap["id"] + " (" + cap["name"] + ") score=" + str(cap["score"]) + " keywords=" + str(cap["keywords"]) + "\n")
                sys.stdout.write("Activated experts: " + str(data["expert_count"]) + " (" + str(data["ram_kb"]) + " KB RAM)\n")
                for e in data["activated_experts"]:
                    sys.stdout.write("  " + e["expert"] + " [" + e["layer"] + "/" + e["domain"] + "] for " + e["capability"] + "\n")
            else:
                sys.stdout.write("Route failed: " + str(err) + "\n")
        elif command == "cap_activate":
            capId = args[1] if len(args) > 1 else "python_grammar"
            ok, data, err = capRouter.Run("activate", {"capability_id": capId})
            if ok:
                sys.stdout.write("Activated: " + data["capability"] + " (" + str(data["activated"]) + " experts, " + str(data["ram_kb"]) + " KB)\n")
            else:
                sys.stdout.write("Activate failed: " + str(err) + "\n")
        elif command == "cap_deactivate":
            capId = args[1] if len(args) > 1 else "python_grammar"
            ok, data, err = capRouter.Run("deactivate", {"capability_id": capId})
            if ok:
                sys.stdout.write("Deactivated: " + data["capability"] + " (freed " + str(data["freed_kb"]) + " KB)\n")
            else:
                sys.stdout.write("Deactivate failed: " + str(err) + "\n")
        elif command == "cap_status":
            ok, data, err = capRouter.Run("status", {})
            if ok:
                sys.stdout.write("=== CAPABILITY SYSTEM STATUS ===\n")
                sys.stdout.write("Capabilities: " + str(data["total_capabilities"]) + " | Active experts: " + str(data["total_active_experts"]) + " | RAM: " + str(data["total_ram_kb"]) + " KB\n\n")
                for cap in data["capabilities"]:
                    status = "ACTIVE" if cap["is_active"] else "dormant"
                    sys.stdout.write("  " + cap["id"] + " [" + status + "]\n")
                    sys.stdout.write("    " + cap["name"] + "\n")
                    sys.stdout.write("    Experts: " + str(cap["active_experts"]) + "/" + str(cap["total_experts"]) + " active | RAM: " + str(cap["ram_kb"]) + " KB | Used: " + str(cap["activated_count"]) + "x\n")
            else:
                sys.stdout.write("Status failed: " + str(err) + "\n")
        elif command == "cap_list":
            ok, data, err = capRouter.Run("list_capabilities", {})
            if ok:
                sys.stdout.write("Capabilities (" + str(data["total"]) + "):\n")
                for cap in data["capabilities"]:
                    sys.stdout.write("\n  " + cap["id"] + ": " + cap["name"] + "\n")
                    sys.stdout.write("    " + cap["description"] + "\n")
                    sys.stdout.write("    Experts (" + str(len(cap["experts"])) + "): ")
                    sys.stdout.write(", ".join(e["name"] + "(" + e["state"] + ")" for e in cap["experts"]) + "\n")
                    sys.stdout.write("    Keywords: " + ", ".join(cap["keywords"][:8]) + "...\n")
            else:
                sys.stdout.write("List failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command in ("gen_all", "gen_train", "gen_train_all"):
        generator = CoreMLTrainingGenerator()
        if command == "gen_all":
            samples = int(args[1]) if len(args) > 1 else 200
            sys.stdout.write("Generating training data for all 7 layers (" + str(samples) + " samples/domain)...\n")
            sys.stdout.flush()
            ok, data, err = generator.Run("gen_all", {"samples": samples})
            if ok:
                sys.stdout.write("Generated " + str(data["layers_generated"]) + " layers, " + str(data["total_samples"]) + " total samples:\n")
                for r in data["results"]:
                    sys.stdout.write("  " + r["layer"] + ": " + str(r["samples"]) + " samples -> " + r["path"] + "\n")
            else:
                sys.stdout.write("Gen failed: " + str(err) + "\n")
        elif command == "gen_train":
            layer = args[1] if len(args) > 1 else "grammar"
            domain = args[2] if len(args) > 2 else "vscode"
            epochs = int(args[3]) if len(args) > 3 else 300
            samples = int(args[4]) if len(args) > 4 else 200
            sys.stdout.write("Training generated " + layer + "/" + domain + " (" + str(epochs) + " epochs, " + str(samples) + " samples)...\n")
            sys.stdout.flush()
            ok, data, err = generator.Run("train_generated", {"layer": layer, "domain": domain, "epochs": epochs, "samples": samples})
            if ok:
                sys.stdout.write("Trained: " + data["layer"] + "/" + data["domain"] + "\n")
                sys.stdout.write("  Samples: " + str(data["samples"]) + "\n")
                sys.stdout.write("  " + data["first_loss"] + "\n")
                sys.stdout.write("  " + data["last_loss"] + "\n")
                sys.stdout.write("  Weights: " + data["output_weights"] + "\n")
            else:
                sys.stdout.write("Train failed: " + str(err) + "\n")
        elif command == "gen_train_all":
            epochs = int(args[1]) if len(args) > 1 else 300
            samples = int(args[2]) if len(args) > 2 else 200
            sys.stdout.write("Training ALL generated experts (7 layers x 5 domains = 35 experts)...\n")
            sys.stdout.write("  " + str(samples) + " samples/domain, " + str(epochs) + " epochs each\n")
            sys.stdout.flush()
            ok, data, err = generator.Run("train_all_generated", {"epochs": epochs, "samples": samples})
            if ok:
                sys.stdout.write("Trained " + str(data["trained"]) + "/" + str(data["total"]) + " experts:\n")
                for r in data["results"]:
                    status = "OK" if r.get("success") else "FAIL"
                    sys.stdout.write("  " + r["layer"] + "/" + r["domain"] + ": " + status + " | " + r.get("first_loss", "") + " -> " + r.get("last_loss", "") + "\n")
            else:
                sys.stdout.write("Train all failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command in ("tf_list", "tf_apply", "tf_train", "tf_train_all", "tf_classify"):
        transformer = CoreMLASTTransformer()
        if command == "tf_list":
            ok, data, err = transformer.Run("list_transforms", {})
            if ok:
                sys.stdout.write("AST Transformations (" + str(data["total"]) + "):\n")
                for t in data["transformations"]:
                    safety = "SAFE" if t["safe"] else "UNSAFE"
                    sys.stdout.write("  [" + str(t["id"]) + "] " + t["name"] + " [" + safety + "]\n")
                    sys.stdout.write("    " + t["description"] + "\n")
                    sys.stdout.write("    Effects: " + ", ".join(t["effects"]) + "\n")
            else:
                sys.stdout.write("List failed: " + str(err) + "\n")
        elif command == "tf_apply":
            domain = args[1] if len(args) > 1 else "vscode"
            transformId = int(args[2]) if len(args) > 2 else 0
            ok, data, err = transformer.Run("apply_transform", {"domain": domain, "transform_id": transformId})
            if ok:
                safety = "SAFE" if data["safe"] else "UNSAFE"
                sys.stdout.write("Transformation: " + data["transformation"] + " [" + safety + "]\n")
                sys.stdout.write("Domain: " + data["domain"] + "\n")
                sys.stdout.write("Description: " + data["description"] + "\n")
                sys.stdout.write("Feature deltas:\n")
                for d in data["deltas"]:
                    sys.stdout.write("  " + d["feature"] + ": " + str(d["before"]) + " -> " + str(d["after"]) + " (delta=" + str(d["delta"]) + ")\n")
            else:
                sys.stdout.write("Apply failed: " + str(err) + "\n")
        elif command == "tf_train":
            domain = args[1] if len(args) > 1 else "vscode"
            epochs = int(args[2]) if len(args) > 2 else 300
            samples = int(args[3]) if len(args) > 3 else 200
            sys.stdout.write("Training transform expert for " + domain + " (" + str(epochs) + " epochs, " + str(samples) + " samples)...\n")
            sys.stdout.flush()
            ok, data, err = transformer.Run("train_transform", {"domain": domain, "epochs": epochs, "samples": samples})
            if ok:
                sys.stdout.write("Trained: " + data["domain"] + " (" + data["mode"] + ")\n")
                sys.stdout.write("  Samples: " + str(data["samples"]) + "\n")
                sys.stdout.write("  " + data["first_loss"] + "\n")
                sys.stdout.write("  " + data["last_loss"] + "\n")
                sys.stdout.write("  Weights: " + data["output_weights"] + "\n")
            else:
                sys.stdout.write("Train failed: " + str(err) + "\n")
        elif command == "tf_train_all":
            epochs = int(args[1]) if len(args) > 1 else 300
            samples = int(args[2]) if len(args) > 2 else 200
            sys.stdout.write("Training ALL transform experts (5 transform + 5 invariant = 10 experts)...\n")
            sys.stdout.flush()
            ok, data, err = transformer.Run("train_all_transforms", {"epochs": epochs, "samples": samples})
            if ok:
                sys.stdout.write("Trained " + str(data["trained"]) + "/" + str(data["total"]) + " experts:\n")
                for r in data["results"]:
                    status = "OK" if r.get("success") else "FAIL"
                    sys.stdout.write("  " + r["mode"] + "/" + r["domain"] + ": " + status + " | " + r.get("first_loss", "") + " -> " + r.get("last_loss", "") + "\n")
            else:
                sys.stdout.write("Train all failed: " + str(err) + "\n")
        elif command == "tf_classify":
            domain = args[1] if len(args) > 1 else "vscode"
            transformId = int(args[2]) if len(args) > 2 else 0
            ok, data, err = transformer.Run("classify_transform", {"domain": domain, "transform_id": transformId})
            if ok:
                safety = "SAFE" if data["safe"] else "UNSAFE"
                sys.stdout.write("=== TRANSFORM CLASSIFICATION ===\n")
                sys.stdout.write("Domain: " + data["domain"] + "\n")
                sys.stdout.write("Actual transform: " + data["actual_transform"] + " [" + safety + "]\n")
                for d, pred in data["predictions"].items():
                    correct = "CORRECT" if pred["correct"] else "WRONG"
                    sys.stdout.write("  " + d + "_expert: predicted=" + pred["predicted"] + " confidence=" + str(pred["confidence"]) + " [" + correct + "]\n")
            else:
                sys.stdout.write("Classify failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command in ("cur_list", "cur_lesson", "cur_run", "cur_train", "cur_progress"):
        teacher = CoreMLCurriculumTeacher()
        if command == "cur_list":
            ok, data, err = teacher.Run("list_teachers", {})
            if ok:
                sys.stdout.write("Curriculum Teachers (" + str(data["total"]) + "):\n")
                for t in data["teachers"]:
                    sys.stdout.write("\n  " + t["id"] + ": " + t["name"] + "\n")
                    sys.stdout.write("    " + t["description"] + "\n")
                    sys.stdout.write("    Questions: " + ", ".join(t["question_types"]) + "\n")
                    sys.stdout.write("    Difficulty levels: " + str(t["difficulty_levels"]) + "\n")
            else:
                sys.stdout.write("List failed: " + str(err) + "\n")
        elif command == "cur_lesson":
            teacherId = args[1] if len(args) > 1 else "grammar_teacher"
            difficulty = int(args[2]) if len(args) > 2 else 1
            ok, data, err = teacher.Run("run_lesson", {"teacher_id": teacherId, "difficulty": difficulty})
            if ok:
                correct = "CORRECT" if data.get("correct") else "WRONG"
                sys.stdout.write("=== LESSON ===\n")
                sys.stdout.write("Teacher: " + data.get("teacher_id", teacherId) + " | Difficulty: " + str(data.get("difficulty", difficulty)) + "\n")
                sys.stdout.write("Domain: " + str(data.get("domain", "")) + " | Question: " + str(data.get("question_type", "")) + "\n")
                sys.stdout.write("Expected: " + str(data.get("expected_answer", "")) + " | Model: " + str(data.get("model_answer", "")) + " [" + correct + "]\n")
                sys.stdout.write("Explanation: " + str(data.get("explanation", "")) + "\n")
                if data.get("model_output"):
                    sys.stdout.write("Output: " + str(data["model_output"]) + "\n")
            else:
                sys.stdout.write("Lesson failed: " + str(err) + "\n")
        elif command == "cur_run":
            lessons = int(args[1]) if len(args) > 1 else 10
            maxDiff = int(args[2]) if len(args) > 2 else 5
            sys.stdout.write("Running curriculum: " + str(lessons) + " lessons/level, " + str(maxDiff) + " levels...\n")
            sys.stdout.flush()
            ok, data, err = teacher.Run("run_curriculum", {"lessons": lessons, "max_difficulty": maxDiff})
            if ok:
                sys.stdout.write("\nOverall: " + str(data["total_correct"]) + "/" + str(data["total_lessons"]) + " correct (" + str(data["overall_accuracy"]) + ")\n\n")
                for r in data["results"]:
                    bar = "#" * int(r["accuracy"] * 20) + "." * (20 - int(r["accuracy"] * 20))
                    sys.stdout.write("  " + r["teacher_id"] + " L" + str(r["difficulty"]) + ": [" + bar + "] " + str(r["accuracy"]) + " (" + str(r["correct"]) + "/" + str(r["lessons"]) + ")\n")
            else:
                sys.stdout.write("Curriculum failed: " + str(err) + "\n")
        elif command == "cur_train":
            teacherId = args[1] if len(args) > 1 else "grammar_teacher"
            domain = args[2] if len(args) > 2 else "vscode"
            epochs = int(args[3]) if len(args) > 3 else 300
            sys.stdout.write("Training curriculum: " + teacherId + "/" + domain + " (" + str(epochs) + " epochs/level)...\n")
            sys.stdout.flush()
            ok, data, err = teacher.Run("train_curriculum", {"teacher_id": teacherId, "domain": domain, "epochs": epochs})
            if ok:
                sys.stdout.write("Trained " + str(data["levels_trained"]) + " levels -> " + data["weights"] + "\n")
                for r in data["results"]:
                    status = "PASS" if r["passed"] else "FAIL"
                    sys.stdout.write("  Level " + str(r["difficulty"]) + ": " + status + " | " + r["first_loss"] + " -> " + r["last_loss"] + " | accuracy=" + str(r["accuracy"]) + "\n")
            else:
                sys.stdout.write("Train failed: " + str(err) + "\n")
        elif command == "cur_progress":
            ok, data, err = teacher.Run("track_progress", {})
            if ok:
                sys.stdout.write("Learning Progress (" + str(data["total_entries"]) + " entries):\n")
                for p in data["progress"]:
                    sys.stdout.write("  " + p["teacher_id"] + " L" + str(p["difficulty"]) + ": " + str(p["correct_count"]) + "/" + str(p["total_lessons"]) + " (" + str(p["accuracy"]) + ")\n")
            else:
                sys.stdout.write("Progress failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command in ("rule_list", "rule_prereq", "rule_lesson", "rule_run", "rule_train", "rule_train_all", "rule_mastery"):
        rules = CoreMLGenerativeRules()
        if command == "rule_list":
            ok, data, err = rules.Run("list_rules", {})
            if ok:
                sys.stdout.write("Generative Rules (" + str(data["total"]) + "):\n")
                for r in data["rules"]:
                    prereqs = ", ".join(r["prerequisite_names"]) if r["prerequisite_names"] else "none"
                    sys.stdout.write("\n  [" + str(r["id"]) + "] " + r["name"] + " (" + r["category"] + ", difficulty " + str(r["difficulty"]) + ")\n")
                    sys.stdout.write("    Rule: " + r["statement"] + "\n")
                    sys.stdout.write("    Why: " + r["rationale"] + "\n")
                    sys.stdout.write("    When: " + r["applies_when"] + "\n")
                    sys.stdout.write("    Not when: " + r["does_not_apply"] + "\n")
                    sys.stdout.write("    Prerequisites: " + prereqs + "\n")
            else:
                sys.stdout.write("List failed: " + str(err) + "\n")
        elif command == "rule_prereq":
            ruleId = int(args[1]) if len(args) > 1 else 8
            ok, data, err = rules.Run("show_prerequisites", {"rule_id": ruleId})
            if ok:
                sys.stdout.write("Prerequisite chain for: " + data["rule"] + " (difficulty " + str(data["difficulty"]) + ")\n")
                sys.stdout.write("  Can study now: " + ("YES" if data["can_study"] else "NO") + "\n")
                for item in data["prerequisite_chain"]:
                    indent = "  " * item["depth"]
                    sys.stdout.write(indent + "-> " + item["rule"] + " (difficulty " + str(item["difficulty"]) + ") needed for " + item["needed_for"] + "\n")
            else:
                sys.stdout.write("Prereq failed: " + str(err) + "\n")
        elif command == "rule_lesson":
            ruleId = int(args[1]) if len(args) > 1 else 0
            ok, data, err = rules.Run("run_rule_lesson", {"rule_id": ruleId})
            if ok:
                correct = "CORRECT" if data.get("correct") else "WRONG"
                sys.stdout.write("=== RULE LESSON ===\n")
                sys.stdout.write("Rule: " + data["rule_name"] + " (difficulty " + str(data["difficulty"]) + ")\n")
                sys.stdout.write("Question: " + data["question_type"] + " | Domain: " + data["domain"] + "\n")
                sys.stdout.write("Statement: " + data["statement"] + "\n")
                sys.stdout.write("Expected: " + str(data["expected_answer"]) + " | Model: " + str(data["model_answer"]) + " [" + correct + "]\n")
                sys.stdout.write("Explanation: " + data["explanation"] + "\n")
                if data.get("model_output"):
                    sys.stdout.write("Output: " + str(data["model_output"]) + "\n")
            else:
                sys.stdout.write("Lesson failed: " + str(err) + "\n")
        elif command == "rule_run":
            lessons = int(args[1]) if len(args) > 1 else 10
            sys.stdout.write("Running rule curriculum: " + str(lessons) + " lessons/rule...\n")
            sys.stdout.flush()
            ok, data, err = rules.Run("run_rule_curriculum", {"lessons": lessons})
            if ok:
                sys.stdout.write("\nOverall: " + str(data["total_correct"]) + "/" + str(data["total_lessons"]) + " (" + str(data["overall_accuracy"]) + ")\n\n")
                for r in data["results"]:
                    bar = "#" * int(r["accuracy"] * 20) + "." * (20 - int(r["accuracy"] * 20))
                    sys.stdout.write("  [" + bar + "] " + r["rule_name"] + " D" + str(r["difficulty"]) + ": " + str(r["accuracy"]) + " (" + str(r["correct"]) + "/" + str(r["lessons"]) + ")\n")
            else:
                sys.stdout.write("Run failed: " + str(err) + "\n")
        elif command == "rule_train":
            ruleId = int(args[1]) if len(args) > 1 else 0
            domain = args[2] if len(args) > 2 else "vscode"
            epochs = int(args[3]) if len(args) > 3 else 300
            sys.stdout.write("Training rule " + str(ruleId) + "/" + domain + " (" + str(epochs) + " epochs)...\n")
            sys.stdout.flush()
            ok, data, err = rules.Run("train_rule", {"rule_id": ruleId, "domain": domain, "epochs": epochs})
            if ok:
                mastered = "MASTERED" if data["mastered"] else "needs more practice"
                sys.stdout.write("Trained: " + data["rule_name"] + " -> " + mastered + "\n")
                sys.stdout.write("  " + data["first_loss"] + "\n")
                sys.stdout.write("  " + data["last_loss"] + "\n")
                sys.stdout.write("  Accuracy: " + str(data["accuracy"]) + "\n")
            else:
                sys.stdout.write("Train failed: " + str(err) + "\n")
        elif command == "rule_train_all":
            domain = args[1] if len(args) > 1 else "vscode"
            epochs = int(args[2]) if len(args) > 2 else 300
            sys.stdout.write("Training ALL rules for " + domain + " (" + str(epochs) + " epochs, prerequisite-gated)...\n")
            sys.stdout.flush()
            ok, data, err = rules.Run("train_all_rules", {"domain": domain, "epochs": epochs})
            if ok:
                sys.stdout.write("Trained: " + str(data["trained"]) + " | Mastered: " + str(data["mastered"]) + "/" + str(data["total_rules"]) + "\n")
                for r in data["results"]:
                    if r.get("skipped"):
                        sys.stdout.write("  [SKIP] " + r["rule_name"] + ": " + r.get("reason", "") + "\n")
                    else:
                        status = "MASTERED" if r.get("mastered") else "practice"
                        sys.stdout.write("  [" + status + "] " + r["rule_name"] + " D" + str(r.get("difficulty", "")) + ": " + r.get("first_loss", "") + " -> " + r.get("last_loss", "") + " | acc=" + str(r.get("accuracy", "")) + "\n")
            else:
                sys.stdout.write("Train all failed: " + str(err) + "\n")
        elif command == "rule_mastery":
            ok, data, err = rules.Run("track_mastery", {})
            if ok:
                sys.stdout.write("Rule Mastery (" + str(data["total"]) + " rules):\n")
                for m in data["mastery"]:
                    status = "MASTERED" if m["is_mastered"] else "learning"
                    bar = "#" * int(m["mastery_score"] * 20) + "." * (20 - int(m["mastery_score"] * 20))
                    sys.stdout.write("  [" + bar + "] " + m["rule_name"] + " D" + str(m["difficulty"]) + ": " + str(m["mastery_score"]) + " (" + str(m["lessons_correct"]) + "/" + str(m["lessons_total"]) + ") [" + status + "]\n")
            else:
                sys.stdout.write("Mastery failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command in ("sr_align", "sr_list", "sr_encode", "sr_space"):
        shared = CoreMLSharedRepresentation()
        if command == "sr_align":
            ok, data, err = shared.Run("align_experts", {})
            if ok:
                sys.stdout.write("Discovered " + str(data["discovered"]) + " experts, registered " + str(data["registered"]) + "\n")
                for e in data["experts"]:
                    sys.stdout.write("  " + e["expert_id"] + " [" + e["expert_type"] + "/" + e["domain"] + "]\n")
            else:
                sys.stdout.write("Align failed: " + str(err) + "\n")
        elif command == "sr_list":
            ok, data, err = shared.Run("list_experts", {"discover": True})
            if ok:
                sys.stdout.write("Expert Registry (" + str(data["total"]) + " experts):\n")
                for t, count in data["type_counts"].items():
                    sys.stdout.write("  " + t + ": " + str(count) + " experts\n")
                sys.stdout.write("\nDetailed listing:\n")
                for e in data["experts"]:
                    exists = "OK" if e["exists"] else "MISSING"
                    sys.stdout.write("  [" + exists + "] " + e["expert_id"] + " | type=" + e["expert_type"] + " | domain=" + e["domain"] + "\n")
            else:
                sys.stdout.write("List failed: " + str(err) + "\n")
        elif command == "sr_encode":
            expertType = args[1] if len(args) > 1 else "layout"
            rawVals = [float(x) for x in args[2:12]] if len(args) > 2 else [0.8, 0.1, 0.05, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            ok, data, err = shared.Run("encode_output", {"expert_type": expertType, "raw_output": rawVals})
            if ok:
                sys.stdout.write("Expert type: " + data["expert_type"] + "\n")
                sys.stdout.write("Raw output:   " + str(data["raw_output"]) + "\n")
                sys.stdout.write("Semantic:     " + str(data["semantic_output"]) + "\n")
                sys.stdout.write("Description:  " + str(data["description"]) + "\n")
            else:
                sys.stdout.write("Encode failed: " + str(err) + "\n")
        elif command == "sr_space":
            featureFile = args[1] if len(args) > 1 else None
            if not featureFile:
                sys.stdout.write("Usage: sr_space <feature_json_file>\n")
                sys.stdout.write("  File must contain a 40-element float array\n")
            else:
                with open(featureFile, "r") as f:
                    features = json.load(f)
                ok, data, err = shared.Run("shared_space", {"features": features})
                if ok:
                    sys.stdout.write("Experts consulted: " + str(data["experts_consulted"]) + "\n")
                    sys.stdout.write("Ensemble semantic: " + str(data["ensemble_semantic"]) + "\n")
                    sys.stdout.write("Description: " + str(data["ensemble_description"]) + "\n")
                else:
                    sys.stdout.write("Space failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command in ("coord_list", "coord_route", "coord_pipeline", "coord_run", "coord_log"):
        coordinator = CoreMLExpertCoordinator()
        if command == "coord_list":
            ok, data, err = coordinator.Run("list_strategies", {})
            if ok:
                sys.stdout.write("Task Types (" + str(data["total_task_types"]) + "):\n")
                for t in data["task_types"]:
                    sys.stdout.write("\n  " + t["id"] + ": " + t["name"] + "\n")
                    sys.stdout.write("    " + t["description"] + "\n")
                    sys.stdout.write("    Experts: " + ", ".join(t["experts_needed"]) + "\n")
                    sys.stdout.write("    Fusion: " + t["fusion_strategy"] + "\n")
                sys.stdout.write("\nFusion Strategies:\n")
                for s in data["fusion_strategies"]:
                    sys.stdout.write("  - " + s + "\n")
                sys.stdout.write("\nExpert Type Weights:\n")
                for t, w in data["expert_type_weights"].items():
                    sys.stdout.write("  " + t + ": " + str(w) + "\n")
            else:
                sys.stdout.write("List failed: " + str(err) + "\n")
        elif command == "coord_route":
            taskDesc = " ".join(args[1:]) if len(args) > 1 else "full analysis"
            ok, data, err = coordinator.Run("route", {"task_description": taskDesc})
            if ok:
                sys.stdout.write("Task: " + data["task_description"] + "\n")
                sys.stdout.write("Routed to: " + data["routed_task"] + " (" + data["task_name"] + ")\n")
                sys.stdout.write("Fusion strategy: " + data["fusion_strategy"] + "\n")
                sys.stdout.write("Experts needed: " + ", ".join(data["experts_needed"]) + "\n")
                sys.stdout.write("Available: " + str(data["experts_available"]) + "\n")
            else:
                sys.stdout.write("Route failed: " + str(err) + "\n")
        elif command == "coord_pipeline":
            taskDesc = " ".join(args[1:]) if len(args) > 1 else "full analysis"
            ok, data, err = coordinator.Run("show_pipeline", {"task_description": taskDesc})
            if ok:
                sys.stdout.write("Coordination Pipeline for: " + data["task_name"] + "\n")
                sys.stdout.write("Fusion: " + data["fusion_strategy"] + " | Steps: " + str(data["total_steps"]) + "\n\n")
                for step in data["pipeline"]:
                    sys.stdout.write("  Step " + str(step["step"]) + ": " + step["expert_type"] + " (" + str(step["available_experts"]) + " experts, weight=" + str(step["weight"]) + ")\n")
                    if step["expert_ids"]:
                        sys.stdout.write("    IDs: " + ", ".join(step["expert_ids"][:5]) + "\n")
            else:
                sys.stdout.write("Pipeline failed: " + str(err) + "\n")
        elif command == "coord_run":
            taskDesc = args[1] if len(args) > 1 else "full analysis"
            featureFile = args[2] if len(args) > 2 else None
            if not featureFile:
                sys.stdout.write("Usage: coord_run <task_description> <feature_json_file>\n")
            else:
                with open(featureFile, "r") as f:
                    features = json.load(f)
                ok, data, err = coordinator.Run("coordinate", {"features": features, "task_description": taskDesc})
                if ok:
                    sys.stdout.write("=== COORDINATION RESULT ===\n")
                    sys.stdout.write("Task: " + data.get("task", "") + " (" + data.get("task_name", "") + ")\n")
                    sys.stdout.write("Fusion: " + data.get("fusion_strategy", "") + "\n")
                    sys.stdout.write("Experts consulted: " + str(data.get("experts_consulted", 0)) + "\n")
                    if data.get("expert_details"):
                        for ed in data["expert_details"]:
                            sys.stdout.write("  " + ed["expert_id"] + " [" + ed["expert_type"] + "/" + ed["domain"] + "] confidence=" + str(ed["confidence"]) + "\n")
                    sys.stdout.write("\nEnsemble: " + str(data.get("ensemble_semantic", [])) + "\n")
                    sys.stdout.write("Description: " + str(data.get("ensemble_description", [])) + "\n")
                    sys.stdout.write("Confidence: " + str(data.get("confidence", 0)) + "\n")
                    sys.stdout.write("Top expert: " + str(data.get("top_expert", "")) + "\n")
                else:
                    sys.stdout.write("Coordination failed: " + str(err) + "\n")
        elif command == "coord_log":
            limit = int(args[1]) if len(args) > 1 else 10
            ok, data, err = coordinator.Run("coordination_log", {"limit": limit})
            if ok:
                sys.stdout.write("Coordination Log (" + str(data["total"]) + " entries):\n")
                for log in data["logs"]:
                    sys.stdout.write("  [" + log["task_type"] + "] " + log["task_description"] + " | fusion=" + log["fusion_strategy"] + " | confidence=" + str(log["confidence"]) + " | " + log["final_answer"] + "\n")
            else:
                sys.stdout.write("Log failed: " + str(err) + "\n")
        sys.stdout.flush()

    elif command in ("ad_teach", "ad_teach_all", "ad_diagnose", "ad_progress"):
        teacher = CoreMLAdaptiveTeacher()
        if command == "ad_teach":
            ruleId = int(args[1]) if len(args) > 1 else 0
            domain = args[2] if len(args) > 2 else "vscode"
            sys.stdout.write("Adaptive teaching rule " + str(ruleId) + "/" + domain + "...\n")
            sys.stdout.flush()
            ok, data, err = teacher.Run("teach_rule", {"rule_id": ruleId, "domain": domain})
            if ok:
                status = "MASTERED" if data["mastered"] else "NOT MASTERED"
                sys.stdout.write("\n" + data["rule_name"] + " D" + str(data["difficulty"]) + ": " + status + " (" + str(data["retries"]) + " retries, acc=" + str(data["final_accuracy"]) + ")\n")
                for entry in data["retry_log"]:
                    tag = "INITIAL" if entry["retry"] == 0 else "RETRY " + str(entry["retry"])
                    typesStr = ", ".join(entry.get("failed_types", [])) if entry.get("failed_types") else "none"
                    sys.stdout.write("  [" + tag + "] acc=" + str(entry["accuracy"]) + " | failed: " + typesStr)
                    if entry.get("noise") is not None:
                        sys.stdout.write(" | noise=" + str(entry["noise"]) + " delta=" + str(entry["delta"]))
                    sys.stdout.write("\n")
                    for qt, score in entry.get("type_scores", {}).items():
                        bar = "#" * int(score * 20) + "." * (20 - int(score * 20))
                        sys.stdout.write("    " + qt + " [" + bar + "] " + str(score) + "\n")
            else:
                sys.stdout.write("Teach failed: " + str(err) + "\n")
        elif command == "ad_teach_all":
            domain = args[1] if len(args) > 1 else "vscode"
            sys.stdout.write("Adaptive teaching ALL rules for " + domain + " (prerequisite-gated, auto-retry)...\n")
            sys.stdout.flush()
            ok, data, err = teacher.Run("teach_all", {"domain": domain})
            if ok:
                sys.stdout.write("\nTrained: " + str(data["trained"]) + " | Mastered: " + str(data["mastered"]) + "/" + str(data["total_rules"]) + "\n\n")
                for r in data["results"]:
                    if r.get("skipped"):
                        sys.stdout.write("  [SKIP] " + r["rule_name"] + ": " + r.get("reason", "") + "\n")
                    else:
                        status = "MASTERED" if r.get("mastered") else "NOT MASTERED"
                        retries = r.get("retries", 0)
                        acc = r.get("final_accuracy", 0)
                        sys.stdout.write("  [" + status + "] " + r["rule_name"] + " D" + str(r.get("difficulty", "")) + " | retries=" + str(retries) + " acc=" + str(acc) + "\n")
                        for qt, score in r.get("type_scores", {}).items():
                            mark = "OK" if score >= 0.8 else "FAIL"
                            sys.stdout.write("    " + qt + ": " + str(score) + " [" + mark + "]\n")
            else:
                sys.stdout.write("Teach all failed: " + str(err) + "\n")
        elif command == "ad_diagnose":
            ruleId = int(args[1]) if len(args) > 1 else 0
            domain = args[2] if len(args) > 2 else "vscode"
            ok, data, err = teacher.Run("diagnose", {"rule_id": ruleId, "domain": domain})
            if ok:
                sys.stdout.write("Diagnosis for " + data["rule_name"] + " (" + domain + "):\n")
                sys.stdout.write("Overall accuracy: " + str(data["overall_accuracy"]) + "\n\n")
                for qt, result in data["type_results"].items():
                    mark = "PASS" if result["accuracy"] >= 0.8 else "FAIL"
                    bar = "#" * int(result["accuracy"] * 20) + "." * (20 - int(result["accuracy"] * 20))
                    sys.stdout.write("  " + qt + " [" + bar + "] " + str(result["accuracy"]) + " (" + str(result["correct"]) + "/" + str(result["total"]) + ") [" + mark + "]\n")
                sys.stdout.write("\nFailed types: " + str(data["failed_types"]) + "\n")
                sys.stdout.write("Passed types: " + str(data["passed_types"]) + "\n")
            else:
                sys.stdout.write("Diagnose failed: " + str(err) + "\n")
        elif command == "ad_progress":
            ok, data, err = teacher.Run("progress", {})
            if ok:
                sys.stdout.write("Adaptive Mastery (" + str(data["total"]) + " rules):\n\n")
                for m in data["mastery"]:
                    status = "MASTERED" if m["is_mastered"] else "learning"
                    bar = "#" * int(m["mastery_score"] * 20) + "." * (20 - int(m["mastery_score"] * 20))
                    sys.stdout.write("  [" + bar + "] " + m["rule_name"] + " D" + str(m["difficulty"]) + ": " + str(m["mastery_score"]) + " retries=" + str(m["retries"]) + " [" + status + "]\n")
                    for qt, score in m.get("question_scores", {}).items():
                        mark = "OK" if score >= 0.8 else "--"
                        sys.stdout.write("    " + qt + ": " + str(score) + " [" + mark + "]\n")
                if data.get("retry_history"):
                    sys.stdout.write("\nRecent Retries:\n")
                    for r in data["retry_history"][:10]:
                        mastered = "MASTERED" if r["mastered"] else "still learning"
                        sys.stdout.write("  Rule " + str(r["rule_id"]) + " retry " + str(r["retry_num"]) + ": " + str(r["acc_before"]) + " -> " + str(r["acc_after"]) + " [" + mastered + "] failed: " + r["failed_types"] + "\n")
            else:
                sys.stdout.write("Progress failed: " + str(err) + "\n")
        sys.stdout.flush()

    else:
        sys.stdout.write("Unknown command: " + command + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
