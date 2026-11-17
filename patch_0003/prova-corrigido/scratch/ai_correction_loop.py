#!/usr/bin/env python3
"""
AI Correction Loop for Prova.

ESTADO: SIMULADO. Não chama nenhum modelo: `generate_ai_response` devolve um texto de espaço reservado e
o laço não itera. Só a parte de ler o JSON de `prova.py check --json` e resumir os erros é real.

End-to-end loop:
1. IA generates Prova code
2. Tool checks the code and returns structured JSON errors
3. IA uses the errors to rewrite/fix the code
4. Repeat until all obligations are proved

Usage:
    python ai_correction_loop.py --generate | python prova.py check --json | python ai_correction_loop.py --interpret
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prova  # noqa: E402


def run_check(filepath):
    """Run prova check and return JSON results."""
    import subprocess
    abs_filepath = os.path.abspath(filepath)
    result = subprocess.run(
        ["python", "prova.py", "check", abs_filepath, "--json"],
        capture_output=True, text=True
    )
    try:
        data = json.loads(result.stdout)
        return data
    except json.JSONDecodeError:
        print(f"Erro ao decodificar JSON: {result.stdout}", file=sys.stderr)
        return None


def format_errors_for_ai(results):
    """Format check results into AI-friendly structure.
    
    Returns a list of error summaries that the IA can use to fix the code.
    `results` is a list of function result dicts from prova.py check --json.
    Only includes obligations with status != 'proved' and linear errors.
    """
    if not results:
        return []
    
    ai_feedback = []
    for r in results:
        if isinstance(r, dict) and r.get("fn"):
            fn_name = r["fn"]
            
            # Include linear errors (always relevant)
            for le in r.get("linear_errors", []):
                error_entry = {
                    "function": fn_name,
                    "label": le,
                    "goal": "",
                    "status": "linear_error",
                }
                ai_feedback.append(error_entry)
            
            # Include obligation errors that are not proved
            for ob in r.get("obligations", []):
                status = ob.get("status", "unknown")
                if status == "proved":
                    continue  # Skip proved obligations
                
                label = ob.get("label", "")
                goal = ob.get("goal", "")
                model = ob.get("model", {})
                note = ob.get("note", "")
                
                error_entry = {
                    "function": fn_name,
                    "label": label,
                    "goal": goal,
                    "status": status,
                }
                
                if status == "failed" and model:
                    error_entry["counterexample"] = model
                
                if note:
                    error_entry["note"] = note
                
                ai_feedback.append(error_entry)
    
    return ai_feedback


def generate_ai_response(feedback):
    """Simulate IA generating corrected code based on feedback.
    
    In a real scenario, this would call an LLM API. Here we just
    print the feedback that the IA should respond to.
    """
    print("\n=== IA FEEDBACK ===")
    for entry in feedback:
        print(f"\nFuncao: {entry['function']}")
        print(f"Rotulo: {entry['label']}")
        print(f"Objetivo: {entry['goal'][:100]}..." if len(entry.get('goal', '')) > 100 else f"Objetivo: {entry['goal']}")
        print(f"Status: {entry['status']}")
        if 'counterexample' in entry:
            print(f"Contraexemplo: {entry['counterexample']}")
        if 'note' in entry:
            print(f"Nota: {entry['note']}")
    print("==================\n")
    
    # Return "corrected" code placeholder
    return '# IA would generate corrected code here\n'


def main():
    if len(sys.argv) < 2:
        print("Usage: python ai_correction_loop.py [--generate|--interpret] [file]")
        print("--generate: Generate initial code (simulated)")
        print("--interpret: Check code and format errors for IA")
        sys.exit(1)
    
    mode = sys.argv[1]
    
    if mode == "--generate":
        # Simulate IA generating Prova code
        print(";; IA-generated Prova code (example)")
        print("(fn sum_to")
        print("  (params (n usize))")
        print("  (returns i64)")
        print("  (pre)")
        print("  (post (= result (* n (+ n 1) 1/2)))")
        print("  (body")
        print("    (let S i64 0)")
        print("    (let i usize 0)")
        print("    (while (< i n)")
        print("      (invariant (<= 0 S))")
        print("      (decreases (- n i))")
        print("      (set S (+ S i))")
        print("      (set i (+ i 1)))")
        print("    (return S))")
        
    elif mode == "--interpret":
        if len(sys.argv) < 3:
            print("Error: Need file argument for --interpret mode")
            sys.exit(1)
        
        filepath = sys.argv[2]
        print(f"\n=== Checking {filepath} ===\n")
        
        # Run check
        results = run_check(filepath)
        
        if results is None:
            print("Failed to get check results")
            sys.exit(1)
        
        # Format feedback for IA
        feedback = format_errors_for_ai(results)
        
        if not feedback:
            print("No errors found - all obligations proved!")
            return
        
        # Generate AI response
        print("=== IA CORRECTION LOOP ===")
        print(f"Found {len(feedback)} error(s) needing correction:")
        for i, f in enumerate(feedback, 1):
            print(f"\n{i}. {f['function']}: {f['label']}")
            print(f"   Goal: {f['goal'][:80]}...")
        
        # Simulate IA generating corrected code
        print("\n--- IA generates corrected code ---")
        corrected = generate_ai_response(feedback)
        print(corrected)
        
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)


if __name__ == "__main__":
    main()