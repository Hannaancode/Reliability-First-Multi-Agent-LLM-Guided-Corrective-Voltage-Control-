"""Fresh-process restore of all four saved source-policy cursors, no physics."""
import json,os,sys,time
from pathlib import Path
from reflection118_chronological_core_20261022 import *
P=R/'outputs/published_graph118_paid_transition_20261022';O=R/'outputs/published_graph118_fresh_process_cursor_20261022'
def main():
    O.mkdir(exist_ok=False);began=time.monotonic();put(O/'owner.claim',dict(actual_pid=os.getpid(),parent_pid=os.getppid(),source_sha256=sha(__file__)))
    while not (O/'Launcher_ACK.json').exists():assert time.monotonic()-began<120;time.sleep(.1)
    ack=read(O/'Launcher_ACK.json');assert ack['fresh_exact_source_PID_parent_command'] and ack['actual_pid']==os.getpid() and ack['actual_parent_pid']==os.getppid()
    import candidate_process_runtime
    sys.path.append(str(R/'work/physics_env/Lib/site-packages'))
    import pandapower as pp,numpy as np,pandas as pd
    def forbidden(*a,**k):raise BaseException('FRESH_CURSOR_RESTORE_FORBIDS_PF_MODEL')
    pp.runpp=forbidden
    from published_graph118_backend_20261022 import Graph118Env,author_policy
    prior=read(P/'Saved_Transition_And_Cursor_Readiness.json');assert prior['status'].startswith('PASS_ALL4_SAVED_FEEDBACK')
    Policy,astsha=author_policy(O);assert astsha==prior['author_policy_class_AST_sha256'];rows=[]
    for i,rec in enumerate(prior['rows']):
        state=decode(P,rec['cursor']);assert state['action_count']==1 and state['absolute_native_action_cap']==136 and state['author_AST_sha256']==astsha
        env=Graph118Env(state['net'],O);env.gen_obs_data=state['gen_obs_data'];env.shunt_status_arr=state['shunt_status']
        agent=Policy(env=env,file_str='fresh_'+str(i),random=False);vars(agent).update(state['agent_fields'])
        assert len(state['action_history'])==1
        action=int(agent.get_action(state['action_history']));assert action==rec['hypothetical_next_action_id'] and env.decode(action)==rec['hypothetical_next_action']
        assert env.saw.calls==0,'The pinned initial graph must be restored, not rebuilt from successor admittance'
        rows.append(dict(case_id=rec['case_id'],cursor_sha256=rec['cursor']['sha256'],next_action=env.decode(action),next_action_exact=True,source_native_action_cap=136,new_PF_model_commit_calls=0))
    put(O/'Fresh_Process_Cursor_Audit.json',dict(status='PASS_ALL4_ACTUAL_FRESH_PROCESS_SOURCE_CURSOR_AND_NEXT_CHOICE',rows=rows,
        actual_pid=os.getpid(),parent_pid=os.getppid(),actual_process_was_launcher_bound=True,source_sha256=sha(__file__),
        not_an_actual_physical_trajectory_or_new_commit=True,full_rollout_ownership_history_cost_reader_protocol_still_required=True,
        all_new_PF_model_optimizer_training_calls=0,workflow_seconds=time.monotonic()-began))
    put(O/'Closed_Manifest.json',dict(members={p.name:sha(p) for p in O.iterdir() if p.is_file()}))
if __name__=='__main__':main()
