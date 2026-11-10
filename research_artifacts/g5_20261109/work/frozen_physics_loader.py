"""CPU-only definition loader; no model execution or original-file edits.

Keeps every function AST unchanged. Imports, scalar/container config assignments,
and definitions are executed; I/O/setup/main statements are explicitly omitted.
The original numerical controller functions are linked to the same dependencies.
"""
import ast,types,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent/'e'
AUDIT=[]
def load(name,path,links=None):
    text=path.read_text(encoding='utf-8');tree=ast.parse(text);kept=[];omitted=[]
    for n in tree.body:
        keep=isinstance(n,(ast.FunctionDef,ast.ClassDef))
        if isinstance(n,ast.Import):
            keep=not any(a.name in ['torch','phase2d_iterative_blackboard_v0','phase2g_llm_guided_rescue_runner'] for a in n.names)
        elif isinstance(n,ast.ImportFrom):keep=n.module!='unsloth'
        elif isinstance(n,ast.Assign):
            keep=all(isinstance(t,ast.Name) and t.id.isupper() for t in n.targets) or all(isinstance(t,ast.Tuple) and all(isinstance(e,ast.Name) and e.id.isupper() for e in t.elts) for t in n.targets)
        if keep:kept.append(n)
        else:omitted.append({'line':n.lineno,'statement':ast.unparse(n).splitlines()[0]})
    original_defs=[ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,ast.FunctionDef)]
    selected_defs=[ast.dump(n,include_attributes=False) for n in kept if isinstance(n,ast.FunctionDef)]
    assert original_defs==selected_defs
    mod=types.ModuleType(name);mod.__file__=str(path);mod.__dict__.update(links or {})
    exec(compile(ast.Module(body=kept,type_ignores=[]),str(path),'exec'),mod.__dict__)
    AUDIT.append({'file':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'all_function_asts_unchanged':True,'omitted':omitted})
    return mod
def load_stack():
    v0=load('v0',ROOT/'pack/scripts/phase2d_iterative_blackboard_v0.py')
    v2=load('v2',ROOT/'audit/phase2d_iterative_blackboard_v2_deficit_aware.py',{'v0':v0})
    base=load('base_runner',ROOT/'audit/phase2g_multiagent_llm_runner.py')
    rescue=load('rescue',ROOT/'audit/phase2g_rescue_runner.py',{'r':base})
    runner=load('runner',ROOT/'audit/phase2g_llm_guided_rescue_runner.py',{'rescue':rescue,'base_runner':base})
    reflection=load('reflection',ROOT/'audit/run_reflection_v4_safety_envelope.py',{'runner':runner})
    runner.MAX_ITERATIONS=25 # exactly original reflection wrapper line 31
    return v2,runner,reflection
