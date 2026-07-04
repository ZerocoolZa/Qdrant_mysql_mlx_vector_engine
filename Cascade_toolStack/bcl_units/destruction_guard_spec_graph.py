#!/usr/bin/env python3
"""
Spec graph for destruction_guard - understand pattern matching logic
"""

import tkinter as tk
from tkinter import ttk

# Classes and their relationships
CLASSES = {
    "DestructionGuard": {
        "category": "main",
        "methods": ["Init", "Run", "Close", "State", "Evaluate", "TeachBlock", "TeachAllow", "TeachList", "TeachStats", "TeachExport", "TeachImport", "MatchesPattern", "CalculateRisk", "CalculateConfidence", "RecordDecision", "RecordFeedback", "AutoLearn"]
    },
    "PatternMatcher": {
        "category": "core",
        "methods": ["MatchesPattern", "CompileRegex", "InvalidateCache", "CompactCache"]
    },
    "RiskCalculator": {
        "category": "core", 
        "methods": ["CalculateRisk", "CalculateConfidence", "GetSeverity"]
    },
    "Database": {
        "category": "storage",
        "methods": ["InitDB", "LoadPatterns", "SavePattern", "QueryPatterns"]
    },
    "Learner": {
        "category": "learning",
        "methods": ["RecordDecision", "RecordFeedback", "AutoLearn", "RefreshPatternCount"]
    }
}

# Edges showing dependencies
EDGES = [
    ("DestructionGuard", "PatternMatcher", "uses"),
    ("DestructionGuard", "RiskCalculator", "uses"),
    ("DestructionGuard", "Database", "uses"),
    ("DestructionGuard", "Learner", "uses"),
    ("Evaluate", "PatternMatcher", "calls"),
    ("Evaluate", "RiskCalculator", "calls"),
    ("TeachBlock", "Database", "calls"),
    ("TeachAllow", "Database", "calls"),
    ("AutoLearn", "Database", "calls"),
    ("AutoLearn", "PatternMatcher", "calls"),
]

# Pattern types
PATTERN_TYPES = {
    "regex": "Regular expression matching",
    "glob": "Shell glob patterns (*, ?, [])",
    "path": "File path matching",
    "literal": "Exact string match"
}

# Database schema
DB_SCHEMA = {
    "patterns": {
        "columns": ["id", "pattern", "action", "category", "severity", "confidence", "source", "description", "pattern_type", "created_at", "success_count", "failure_count", "last_used"],
        "purpose": "Store all pattern matching rules"
    },
    "decisions": {
        "columns": ["id", "command", "action", "risk_score", "confidence", "matched_patterns", "timestamp"],
        "purpose": "Record all guard decisions"
    },
    "feedback": {
        "columns": ["id", "pattern_id", "was_correct", "timestamp"],
        "purpose": "User feedback on pattern accuracy"
    }
}

def draw_graph():
    root = tk.Tk()
    root.title("DestructionGuard Spec Graph")
    root.geometry("1200x800")
    
    canvas = tk.Canvas(root, bg="#1e1e1e")
    canvas.pack(fill=tk.BOTH, expand=True)
    
    # Draw classes
    x_offset = 100
    y_offset = 100
    for class_name, info in CLASSES.items():
        x = x_offset
        y = y_offset
        
        # Draw class box
        canvas.create_rectangle(x, y, x + 200, y + 150, fill="#2d2d2d", outline="#4a9eff", width=2)
        canvas.create_text(x + 100, y + 20, text=class_name, fill="#ffffff", font=("Arial", 12, "bold"))
        
        # Draw methods
        method_y = y + 50
        for method in info["methods"]:
            canvas.create_text(x + 100, method_y, text=f"• {method}", fill="#cccccc", font=("Arial", 9))
            method_y += 15
        
        x_offset += 250
        if x_offset > 1000:
            x_offset = 100
            y_offset += 200
    
    # Draw edges
    for src, dst, relation in EDGES:
        canvas.create_line(0, 0, 0, 0, fill="#ff6b6b", arrow=tk.LAST, width=2)
    
    # Draw legend
    canvas.create_text(600, 750, text="Blue = Classes, Red = Dependencies", fill="#ffffff", font=("Arial", 10))
    
    # Draw pattern types info
    info_text = "Pattern Types:\n"
    for ptype, desc in PATTERN_TYPES.items():
        info_text += f"  {ptype}: {desc}\n"
    
    canvas.create_text(900, 400, text=info_text, fill="#98c379", font=("Arial", 10), anchor="w")
    
    # Draw database schema
    schema_text = "Database Schema:\n"
    for table, info in DB_SCHEMA.items():
        schema_text += f"\n{table}:\n"
        schema_text += f"  Purpose: {info['purpose']}\n"
        schema_text += f"  Columns: {', '.join(info['columns'])}\n"
    
    canvas.create_text(100, 400, text=schema_text, fill="#e5c07b", font=("Arial", 9), anchor="w")
    
    root.mainloop()

if __name__ == "__main__":
    draw_graph()
