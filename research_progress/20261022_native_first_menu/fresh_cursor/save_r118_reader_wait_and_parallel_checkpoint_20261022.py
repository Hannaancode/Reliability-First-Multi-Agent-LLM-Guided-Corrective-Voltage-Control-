"""Save the verified primary closure, exact live reader and one-time wait policy."""
import hashlib,json,subprocess
from datetime import datetime,timezone
from pathlib import Path
R=Path(__file__).resolve().parents[1];O=R/'outputs/r118_first_round_missing_only_handoff_20261022'
def read(p):return json.loads((R/p).read_text('utf-8'))
def sha(p):return hashlib.sha256((R/p).read_bytes()).hexdigest()
def main():
    now=datetime.now(timezone.utc).isoformat();p=read('outputs/r118_first_round_missing_only_execution_20261022/Result.json')
    assert p['closed_records']==2034 and p['failure'] is None and p['costs']['new_PF_attempts']==1989 and p['costs']['new_PF_returns']==1988 and p['costs']['new_PF_exceptions']==1
    assert read('outputs/r118_first_round_missing_only_coordination_20261022/End_ACK.json')['exit_code']==0
    reader=read('outputs/r118_first_round_missing_only_independent_20261022/owner.claim');root=read('outputs/r118_first_round_missing_only_handoff_20261022/owner.claim')
    ack=read('outputs/r118_first_round_missing_only_independent_20261022/Launcher_ACK.json');assert ack['actual_pid']==reader['actual_pid'] and ack['actual_parent_pid']==reader['parent_pid'] and ack['fresh_exact_source_PID_parent_command']
    cp=subprocess.run(['powershell.exe','-NoProfile','-Command',"Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match '(audit_r118_first_round_missing_only|coordinate_r118_first_round_missing_only)' } | Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Depth 3"],capture_output=True,text=True,check=True,timeout=30)
    actors=json.loads(cp.stdout) if cp.stdout.strip() else [];assert any(a['ProcessId']==reader['actual_pid'] and a['ParentProcessId']==reader['parent_pid'] for a in actors)
    cold=read('outputs/published_graph118_fresh_process_cursor_20261022/Fresh_Process_Cursor_Audit.json');assert cold['status'].startswith('PASS_ALL4_ACTUAL_FRESH_PROCESS')
    assert read('outputs/published_graph118_fresh_process_cursor_coordination_20261022/End_ACK.json')['exit_code']==0
    state=dict(at_utc=now,status='PRIMARY_ALL_DECLARED_IDENTITIES_CLOSED_FIRST_NEW_RETURN_READER_LIVE',exec_session=55532,
        actual_reader=reader,actual_coordinator=root,fresh_exact_processes=actors,
        primary_costs=p['costs'],primary_workflow_seconds=p['workflow_seconds'],primary_ended_exit0=True,
        declared_queries=2034,old_native80_reuses=42,prior_contract_unknowns_no_call=3,
        actual_reader_started_utc=read('outputs/r118_first_round_missing_only_reader_coordination_20261022/owner.claim')['at_utc'],reader_bound_seconds=1800,
        one_time_result_check=dict(id='hiergrid-first-menu-audit-result-check',at_local='2026-10-22T23:40:00+03:00',one_occurrence=True,quiet_for_normal_progress=True,delete_at_actual_terminal=True,rearm_only_if_exact_reader_live_and_sole_ready_dependency=True),
        original_three_GPU_study='COMPLETE_AUDITED_FIXED_PRIMARY_GATE_FAIL_ALL_RELEASED',current_GPU_assignments=0,
        external_graph_progress=dict(source_and_serialized_cursors='ALL4_PASS',fresh_process_cursors='ALL4_PASS_ZERO_NEW_PF_MODEL_OR_COMMITS',native_action_cap=136,
          source_semantics='Compatible archived author env pinned; historical dependency revision unknown; author experiment truncate_voltages=False. Preserve native/common role and horizon differences.',
          current_no_full_graph_policy_or_training_campaign_ready=True),
        next_after_closure=['Verify fresh actual reader/coordinator ended and actual End_ACK/Independent_Audit/manifest/Completion. Never infer completion from counts.',
          'If independent PASS, verify Analysis_Lock and run summarize_verified_r118_first_round_20261022.py once only when report output is absent. Report every query/cost/exception/unknown; missing-evidence choices stay unknown, no first-menu-as-episode claim.',
          'Save verified results/tasks/reseacrh progress.txt and publish generated all-query CSV/own proofs with fresh lease and exact downloaded bytes.',
          'A subsequent full original DFF or external native/shared-role policy requires its own exact prospective source/ownership/persistent/fullcost/first-new-replay protocol. No automatic continuation of an ended budget, old science or failed readout.'],
        all6_final_goals='OPEN',no_guaranteed_winner=True,last_verified_GitHub='16c5f4bd18526a8adc0b8fe0b0fc5481981e3418',
        GitHub_receipt='outputs/r118_native_frontier_publication_20261022/Verified_GitHub_Receipt.json',
        new_fresh_process_graph_proof_pending_publication=True,
        original_frozen_assets_literal_DSE_both_branches_full_BOTH_and_all_adverse_unknown_costs_preserved=True,
        forbid=['Duplicate/restart/live edits/resource extension','Repeat old/failed PF or executed independent replays','Outcome-selected Q/menu/root/guard/model/seed/checkpoint rescue','Purchases/quota evasion/account fallback','Treat historical development as unused confirmation'],
        usage_note='Latest usage read allowed ordinary work; scheduled time does not establish a reset or override actual lifecycle.')
    with (O/'Current_Wait_And_Resume.json').open('x',encoding='utf-8') as f:json.dump(state,f,indent=2)
    summary='## Native DFF first-menu measurements closed; sole first-return audit running — '+now+'\n\nAll2034declared identities closed:1989newPFattempts/1988returns/1preservedexception,42paid80reuses,3contractUNKNOWN/no call. Primary actual18120/26552ENDEDexit0. Sole reader actual'+str(reader['actual_pid'])+'/'+str(reader['parent_pid'])+', coordinator25924/12800,exec55532,reader1800seconds. Fresh exactclaim/source/parent/command verified. No reader rerun, old/failed physics replay or bound extension. Current resume outputs/r118_first_round_missing_only_handoff_20261022/Current_Wait_And_Resume.json. Pinned analyzer only after allactorsENDED/independentPASS; all2034queryCSV,not wholetrajectory or LLMwin. All6goalsOPEN.\n\nThreeGPUencoderarms complete/audited/released; fixedgateFAIL. ParallelpublishedGraphAgent ALL4paid-transition and ACTUALfresh-process cursor/next-choice checks PASS0PF/model/commit. Native cap136/authortruncateFalse recovered from compatiblearchived source; exact historical dependencyUNKNOWN, nofullpolicy/performance admission. Oneestimatedresultcheck23:40Qatar22Oct, deleteat terminal/rearmonlygenuinelylive soledependency; no recurringmonitor. LastGitHub16c5f4bd18526a8adc0b8fe0b0fc5481981e3418/all4exactdownloadbytesPASS.\n\n'
    for path in ['outputs/Unattended_Execution_Runbook.md','outputs/llm_value_development/Next_Phase_Plan.md','RESEARCH_TASKS.md']:
        target=R/path;target.write_text(summary+target.read_text('utf-8'),encoding='utf-8')
    with (R/'reseacrh progress.txt').open('a',encoding='utf-8') as f:f.write('\n\n'+summary)
    tasks=read('outputs/research_tasks_20261014/Tasks.json');tasks.update(latest_verified_update=now,latest_resume=(O/'Current_Wait_And_Resume.json').relative_to(R).as_posix(),current_owned_jobs=[reader,root],current_GPU_assignments=0)
    (R/'outputs/research_tasks_20261014/Tasks.json').write_text(json.dumps(tasks,indent=2),encoding='utf-8')
    with (R/'outputs/full_system_comparison_20261021/Latest_Wait_And_Resume_20261022.json').open('x',encoding='utf-8') as f:json.dump(dict(at_utc=now,newest_active_continuation=(O/'Current_Wait_And_Resume.json').relative_to(R).as_posix()),f,indent=2)
    print(json.dumps(dict(saved=True,actual_reader=reader['actual_pid'],new_return_replays_required=1988,current_GPU_assignments=0,result_check_Qatar='23:40')))
if __name__=='__main__':main()
