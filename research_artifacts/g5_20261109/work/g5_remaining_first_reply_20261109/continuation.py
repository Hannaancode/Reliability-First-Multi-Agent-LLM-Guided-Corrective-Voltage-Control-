"""Conditional archived-initializer entry; original post-initializer ASTs retained."""
import ast,copy,hashlib
def build_original_post_initializer(original,source_bytes,expected_sha256):
    assert hashlib.sha256(source_bytes).hexdigest()==expected_sha256
    tree=ast.parse(source_bytes.decode('utf-8'));fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run_one_scenario_two_best_v2')
    assert [ast.unparse(n) for n in fn.body[2:5]]==['net = copy.deepcopy(base_net)','net = v2.v0.apply_scenario_to_net(net, scenario, zones)','conv, err = v2.v0.run_pf(net)']
    assert isinstance(fn.body[5],ast.If) and ast.unparse(fn.body[5].test)=='not conv'
    tail=fn.body[6:];assert not any(isinstance(n,ast.Name) and n.id=='base_net' for statement in tail for n in ast.walk(statement))
    args=copy.deepcopy(fn.args);assert args.args[1].arg=='base_net';args.args[1].arg='archived_solved_net'
    replacement=ast.parse('net = copy.deepcopy(archived_solved_net)\nassert bool(net.converged), "Paid archived initializer must already be solved"').body
    new=ast.FunctionDef(name='run_conditional_archived_initializer',args=args,body=copy.deepcopy(fn.body[:2])+replacement+copy.deepcopy(tail),decorator_list=[])
    module=ast.fix_missing_locations(ast.Module(body=[new],type_ignores=[]));env=dict(original.__globals__)
    exec(compile(module,'<source-bound-original-post-initializer>','exec'),env)
    proof={'original_function_AST_sha256':hashlib.sha256(ast.dump(fn,include_attributes=False).encode()).hexdigest(),'original_post_initializer_AST_sha256':hashlib.sha256(ast.dump(ast.Module(body=tail,type_ignores=[]),include_attributes=False).encode()).hexdigest(),'post_initializer_statement_count':len(tail),'all_post_initializer_ASTs_unchanged':True,'changed_input_contract':'CONDITIONAL_ARCHIVED_SOLVED_INITIAL_STATE','removed_prefix':'Base reconstruction/scenario application/initial solve only, paid archived state supplied instead.','no_historical_backend_equality_claim':True}
    return env[new.name],proof
