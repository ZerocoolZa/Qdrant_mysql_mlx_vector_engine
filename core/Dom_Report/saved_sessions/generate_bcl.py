#!/usr/bin/env python3
"""
Read messages 1-40 from SQLite, reason over each non-empty message,
generate a BCL packet, and insert into MySQL chat_message table.

The BCL packets are generated from LLM reasoning over the message content.
"""

import sqlite3
import mysql.connector

# ─── BCL packets generated from LLM reasoning over each message ───
# Each BCL captures what the message IS: entities, concepts, actions, decisions.

BCL_PACKETS = {

    # ── MSG 6 (Assistant) ──
    # "I found the problem. There IS chat pollution — but it's not in the user's
    #  messages. It's in the shell output. Every time I run a command, database
    #  table dumps are being injected into the output. Let me trace the source:"
    6: """[@MESSAGE]
{
    ("msg_num";6)
    ("role";"assistant")
    [@CONTENT]
    {
        ("summary";"Assistant identifies chat pollution in shell output — database table dumps injected after every command, not in user messages — begins tracing the source")
    }
    [@ENTITIES]
    {
        ("type";"artifact";"id";"shell_output";"name";"shell_output")
        ("type";"artifact";"id";"database_table_dumps";"name";"database_table_dumps")
    }
    [@CONCEPTS]
    {
        ("chat_pollution")
        ("shell_output_contamination")
        ("diagnostic_reasoning")
        ("database_dump_injection")
    }
    [@ACTIONS]
    {
        ("identifies";"problem_source")
        ("distinguishes";"user_messages_vs_shell_output")
        ("initiates";"source_tracing")
    }
}""",

    # ── MSG 8 (Assistant) ──
    # "There it is! The ps aux output itself is being polluted with === TABLE:
    #  code_classes dumps. Something is injecting database content into the shell
    #  output after every command. Let me find the source:"
    8: """[@MESSAGE]
{
    ("msg_num";8)
    ("role";"assistant")
    [@CONTENT]
    {
        ("summary";"Assistant observes ps aux output polluted with code_classes table dumps — confirms something is injecting database content into shell output after every command")
    }
    [@ENTITIES]
    {
        ("type";"command";"id";"ps_aux";"name";"ps_aux")
        ("type";"table";"id";"code_classes";"name";"code_classes")
    }
    [@CONCEPTS]
    {
        ("chat_pollution")
        ("process_inspection")
        ("table_dump_injection")
        ("output_contamination")
    }
    [@ACTIONS]
    {
        ("observes";"pollution_in_ps_aux_output")
        ("confirms";"database_content_injection")
        ("investigates";"injection_source")
    }
}""",

    # ── MSG 12 (Assistant) ──
    # "Found it — the declare -f output itself is being polluted with database
    #  dumps. There's a shell function doing this. Let me find it:"
    12: """[@MESSAGE]
{
    ("msg_num";12)
    ("role";"assistant")
    [@CONTENT]
    {
        ("summary";"Assistant discovers declare -f output polluted with database dumps and narrows the cause to a shell function — begins hunting for the specific function")
    }
    [@ENTITIES]
    {
        ("type";"command";"id";"declare_f";"name";"declare_f")
        ("type";"artifact";"id";"shell_function";"name";"shell_function")
    }
    [@CONCEPTS]
    {
        ("chat_pollution")
        ("shell_function_investigation")
        ("database_dump_injection")
        ("function_definition_inspection")
    }
    [@ACTIONS]
    {
        ("identifies";"shell_function_as_cause")
        ("narrows";"pollution_mechanism")
        ("investigates";"specific_shell_function")
    }
}""",

    # ── MSG 16 (Assistant) ──
    # "The pollution appears even when the command itself produces no output.
    #  This means a background process is writing to the terminal. Let me find it:"
    16: """[@MESSAGE]
{
    ("msg_num";16)
    ("role";"assistant")
    [@CONTENT]
    {
        ("summary";"Assistant deduces that pollution appears even with no command output, meaning a background process is independently writing to the terminal")
    }
    [@ENTITIES]
    {
        ("type";"process";"id";"background_process";"name";"background_process")
        ("type";"artifact";"id";"terminal";"name";"terminal")
    }
    [@CONCEPTS]
    {
        ("chat_pollution")
        ("background_process")
        ("terminal_output")
        ("deductive_reasoning")
        ("asynchronous_output_leak")
    }
    [@ACTIONS]
    {
        ("deduces";"background_process_writing_to_terminal")
        ("reasons";"from_absence_of_command_output")
        ("investigates";"background_process")
    }
}""",

    # ── MSG 20 (Assistant) ──
    # "Now I see it. The execution_log table shows a find command for *gemini*
    #  that I never ran. Another process is executing commands and its output
    #  is leaking into this terminal. Let me find it:"
    20: """[@MESSAGE]
{
    ("msg_num";20)
    ("role";"assistant")
    [@CONTENT]
    {
        ("summary";"Assistant discovers execution_log contains a find *gemini* command never run by this agent — evidence that another process is executing commands whose output leaks into this terminal")
    }
    [@ENTITIES]
    {
        ("type";"table";"id";"execution_log";"name";"execution_log")
        ("type";"command";"id";"find_gemini";"name";"find_gemini")
        ("type";"entity";"id";"run_id_286";"name";"run_id_286")
    }
    [@CONCEPTS]
    {
        ("chat_pollution")
        ("execution_log_analysis")
        ("command_attribution")
        ("process_leak")
        ("forensic_evidence")
    }
    [@ACTIONS]
    {
        ("discovers";"foreign_command_in_execution_log")
        ("attributes";"command_to_another_process")
        ("investigates";"leaking_process")
    }
}""",

    # ── MSG 38 (Assistant) ──
    # "The pollution is from cascade_cli.py — it's logging commands to
    #  execution_log and dumping database tables. Another agent (Cascade) is
    #  running in the background and its output is leaking into this terminal.
    #  Let me check what Cascade has been doing:"
    38: """[@MESSAGE]
{
    ("msg_num";38)
    ("role";"assistant")
    [@CONTENT]
    {
        ("summary";"Assistant identifies cascade_cli.py as the pollution source — it logs commands to execution_log and dumps database tables; another agent named Cascade is running in the background with output leaking into this terminal")
    }
    [@ENTITIES]
    {
        ("type";"file";"id";"cascade_cli_py";"name";"cascade_cli.py";"path";"/Users/wws/Downloads/cascade_cli.py")
        ("type";"agent";"id";"Cascade";"name";"Cascade")
        ("type";"table";"id";"execution_log";"name";"execution_log")
    }
    [@CONCEPTS]
    {
        ("chat_pollution")
        ("cascade_agent")
        ("background_process")
        ("output_leak")
        ("database_dump")
        ("agent_identification")
    }
    [@ACTIONS]
    {
        ("identifies";"cascade_cli_py_as_pollution_source")
        ("attributes";"pollution_to_Cascade_agent")
        ("investigates";"Cascade_activity")
    }
}""",

    # ── MSG 40 (Assistant) ──
    # Comprehensive report: confirms chat pollution from cascade_cli.py,
    # lists polluted tables (about_text, code_classes, execution_log),
    # GUI classes (dom_gui, dom_ingest_gui, InstructionsViewer, Core_UefiBoot,
    # GuiSvgExporter, GUI_E_S_engine, Gui_U_C_framework),
    # distinguishes clean architectural content (Method, ComputationUnit, Class,
    # BCL, BCLIR, LAW6), offers to stop the background process.
    40: """[@MESSAGE]
{
    ("msg_num";40)
    ("role";"assistant")
    [@CONTENT]
    {
        ("summary";"Comprehensive diagnostic report confirming chat pollution from cascade_cli.py background process — database table dumps (about_text, code_classes, execution_log) leaking into terminal, GUI content for PyQt6 About dialog misplaced, architectural discussions about Method/ComputationUnit/Class/BCL/BCLIR/LAW6 are clean and unaffected")
    }
    [@ENTITIES]
    {
        ("type";"file";"id";"cascade_cli_py";"name";"cascade_cli.py";"path";"/Users/wws/Downloads/cascade_cli.py")
        ("type";"table";"id";"about_text";"name";"about_text")
        ("type";"table";"id";"code_classes";"name";"code_classes")
        ("type";"table";"id";"execution_log";"name";"execution_log")
        ("type";"table";"id";"c_classes";"name";"c_classes")
        ("type";"table";"id";"code_co_occurrence";"name";"code_co_occurrence")
        ("type";"table";"id";"code_identifier_frequency";"name";"code_identifier_frequency")
        ("type";"class";"id";"dom_gui";"name";"dom_gui")
        ("type";"class";"id";"dom_ingest_gui";"name";"dom_ingest_gui")
        ("type";"class";"id";"InstructionsViewer";"name";"InstructionsViewer")
        ("type";"class";"id";"Core_UefiBoot";"name";"Core_UefiBoot")
        ("type";"class";"id";"GuiSvgExporter";"name";"GuiSvgExporter")
        ("type";"class";"id";"GUI_E_S_engine";"name";"GUI_E_S_engine")
        ("type";"class";"id";"Gui_U_C_framework";"name";"Gui_U_C_framework")
        ("type";"concept";"id";"Method";"name";"Method")
        ("type";"concept";"id";"ComputationUnit";"name";"ComputationUnit")
        ("type";"concept";"id";"Class";"name";"Class")
        ("type";"concept";"id";"BCL";"name";"BCL")
        ("type";"concept";"id";"BCLIR";"name";"BCLIR")
        ("type";"concept";"id";"LAW6";"name";"LAW6")
        ("type";"entity";"id";"run_id_286";"name";"run_id_286")
    }
    [@CONCEPTS]
    {
        ("chat_pollution")
        ("cascade_agent")
        ("background_process")
        ("output_leak")
        ("database_table_dump")
        ("GUI_content")
        ("PyQt6")
        ("VBStyle_architecture")
        ("AES_256_GCM_decryption")
        ("BCL")
        ("BCLIR")
        ("LAW6")
        ("Method")
        ("ComputationUnit")
        ("diagnostic_report")
        ("clean_vs_polluted_content")
        ("cosmetic_pollution")
    }
    [@ACTIONS]
    {
        ("confirms";"chat_pollution_exists")
        ("reports";"polluted_tables")
        ("reports";"GUI_class_dumps")
        ("identifies";"cascade_cli_py_as_source")
        ("distinguishes";"clean_architectural_content_from_pollution")
        ("assesses";"database_work_unaffected")
        ("offers";"to_stop_background_Cascade_process")
    }
}""",
}


def main():
    # ─── Read from SQLite ───
    sqlite_path = "/Users/wws/Qdrant_mysql_mlx_vector_engine/core/Dom_Report/saved_sessions/Devin_Moseimport.db"
    sconn = sqlite3.connect(sqlite_path)
    scur = sconn.cursor()
    scur.execute(
        'SELECT msg_num, role, content FROM messages '
        'WHERE msg_num BETWEEN 1 AND 40 AND role IN ("User","Assistant") '
        'ORDER BY msg_num'
    )
    rows = scur.fetchall()
    sconn.close()

    # ─── Filter: skip empty content ───
    non_empty = [(m, r, c) for (m, r, c) in rows if c and c.strip()]
    print(f"Total messages read from SQLite: {len(rows)}")
    print(f"Non-empty messages to process:   {len(non_empty)}")
    print(f"Skipped (empty content):          {len(rows) - len(non_empty)}")
    print()

    # ─── Connect to MySQL ───
    mconn = mysql.connector.connect(
        host="localhost",
        user="root",
        database="diagnostic_kb",
    )
    mcur = mconn.cursor()

    # Clear existing rows in range to avoid duplicate key errors
    mcur.execute("DELETE FROM chat_message WHERE msg_num BETWEEN 1 AND 40")

    inserted = 0
    for msg_num, role, content in non_empty:
        bcl = BCL_PACKETS.get(msg_num)
        if bcl is None:
            # If we somehow don't have a BCL for this message, skip it
            print(f"  WARNING: No BCL packet for msg_num={msg_num}, skipping")
            continue

        sql = (
            "INSERT INTO chat_message (msg_num, role, content, bcl_packet) "
            "VALUES (%s, %s, %s, %s)"
        )
        mcur.execute(sql, (msg_num, role, content, bcl))
        inserted += 1
        print(f"  Inserted msg_num={msg_num} role={role}")

    mconn.commit()
    mcur.close()
    mconn.close()

    print(f"\nTotal inserted into MySQL: {inserted}")

    # ─── Show 3 example BCL packets ───
    print("\n" + "=" * 80)
    print("EXAMPLE BCL PACKETS (3 samples)")
    print("=" * 80)
    sample_keys = list(BCL_PACKETS.keys())[:3]
    for k in sample_keys:
        print(f"\n--- msg_num={k} ---")
        print(BCL_PACKETS[k])
        print()


if __name__ == "__main__":
    main()
