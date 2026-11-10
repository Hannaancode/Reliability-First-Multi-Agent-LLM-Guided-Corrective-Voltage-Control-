"""Preserve initializer admission evidence; operational failures are not PF outcomes."""
import hashlib,json,traceback
from pathlib import Path

class InitialAdmissionStop(BaseException):
    def __init__(self,kind,payload):self.kind,self.payload=kind,payload
def value_sha(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def compare_and_preserve(net,kwargs,saved_snapshot,expected_kwargs,provenance,snapshot,put,output):
    """No restoration or solve. Snapshot callback is supplied by future admitted owner."""
    output=Path(output)
    try:
        put(output/'Initial_Kwargs_And_Provenance.json',{'actual_kwargs':kwargs,'expected_kwargs':expected_kwargs,'paid_source_provenance':provenance})
        actual=snapshot(net)
        put(output/'Actual_Initial_Input_Before_Admission.json',actual)
        fields=sorted(set(actual)|set(saved_snapshot))
        different=[k for k in fields if k not in actual or k not in saved_snapshot or actual[k]!=saved_snapshot[k]]
        result={'supported_typed_snapshot_equal':actual==saved_snapshot,'exact_kwargs_equal':kwargs==expected_kwargs,
                'actual_snapshot_sha256':value_sha(actual),'saved_snapshot_sha256':value_sha(saved_snapshot),
                'different_top_level_fields':different,'no_projection_normalization_or_field_fill':True,
                'PF_called':False,'native_conversion_called':False,'restoration_performed':False}
        put(output/'Initial_Admission_Comparison.json',result)
        if not result['supported_typed_snapshot_equal'] or not result['exact_kwargs_equal']:
            raise InitialAdmissionStop('INITIAL_PAID_INPUT_NOT_EXACT',result)
        return result
    except InitialAdmissionStop:raise
    except BaseException as exc:
        failure={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc(),
                 'scientific_outcome':'UNKNOWN_NOT_A_SOLVER_FAILURE','PF_called':False,'restoration_performed':False}
        try:put(output/'Initial_Admission_Capture_Failure.json',failure)
        except BaseException as preservation_error:failure['preservation_failure_type']=type(preservation_error).__name__
        raise InitialAdmissionStop('INITIAL_ADMISSION_CAPTURE_INCOMPLETE',failure) from exc

def prevent_solver_translation(callback,put,output):
    """Wrap the entire future provider, including bounds/serialization assertions."""
    def wrapped(*args,**kwargs):
        try:return callback(*args,**kwargs)
        except InitialAdmissionStop:raise
        except BaseException as exc:
            # Other deliberate BaseException frontier classes retain their identity.
            if not isinstance(exc,Exception):raise
            failure={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc(),
                     'scientific_outcome':'UNKNOWN_OPERATIONAL_PROVIDER_FAILURE_NOT_PF_OUTCOME'}
            try:put(Path(output)/'Provider_Admission_Failure.json',failure)
            except BaseException as preservation_error:failure['preservation_failure_type']=type(preservation_error).__name__
            raise InitialAdmissionStop('OPERATIONAL_PROVIDER_FAILURE',failure) from exc
    return wrapped
