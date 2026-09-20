
from __future__ import annotations

GOAL_MODALITIES={"SPEAKING","LISTENING","READING","WRITING"}
EVIDENCE_MODALITIES={"TEXT_PRODUCTION","TEXT_COMPREHENSION","VOICE_PRODUCTION","AUDIO_COMPREHENSION"}

class ModalityContractError(ValueError):
    pass

def classify_observation(obs, runtime):
    """
    Returns:
      PERFORMANCE_EVIDENCE + evidence_modality
      NO_PERFORMANCE_EVIDENCE
      UNSUPPORTED_RUNTIME

    Important: channel != evidence modality.
    """
    ch=obs.get("input_channel")
    task=obs.get("task_contract","FREE_CHAT")
    basis=obs.get("behavior_basis")
    if ch not in {"TEXT","VOICE","AUDIO"}:
        raise ModalityContractError("invalid input_channel")

    # Self-report / exposure alone never becomes performance evidence.
    if basis in {"SELF_REPORT","EXPOSURE_ONLY","MODEL_OPINION","CLICK","ACK"}:
        return {"status":"NO_PERFORMANCE_EVIDENCE","evidence_modality":None}

    if ch=="TEXT":
        if task=="EXPLICIT_TEXT_COMPREHENSION_TASK":
            if not obs.get("genuine_comprehension_opportunity",False):
                return {"status":"NO_PERFORMANCE_EVIDENCE","evidence_modality":None}
            return {"status":"PERFORMANCE_EVIDENCE","evidence_modality":"TEXT_COMPREHENSION"}
        # Free chat and explicit writing task are both text production.
        if basis in {"USER_PRODUCTION","ATTEMPT"}:
            return {"status":"PERFORMANCE_EVIDENCE","evidence_modality":"TEXT_PRODUCTION"}
        return {"status":"NO_PERFORMANCE_EVIDENCE","evidence_modality":None}

    if ch=="VOICE":
        if not runtime.get("voice_input",False):
            return {"status":"UNSUPPORTED_RUNTIME","evidence_modality":None}
        if basis not in {"USER_PRODUCTION","ATTEMPT"}:
            return {"status":"NO_PERFORMANCE_EVIDENCE","evidence_modality":None}
        return {"status":"PERFORMANCE_EVIDENCE","evidence_modality":"VOICE_PRODUCTION"}

    if ch=="AUDIO":
        if not runtime.get("listening_comprehension_evaluator",False):
            return {"status":"UNSUPPORTED_RUNTIME","evidence_modality":None}
        if task!="EXPLICIT_LISTENING_TASK" or not obs.get("genuine_comprehension_opportunity",False):
            return {"status":"NO_PERFORMANCE_EVIDENCE","evidence_modality":None}
        if obs.get("transcript_exposed_before_response",False):
            # Audio-specific attribution is contaminated by text exposure.
            return {"status":"NO_PERFORMANCE_EVIDENCE","evidence_modality":None,
                    "reason":"AUDIO_ATTRIBUTION_CONTAMINATED_BY_TRANSCRIPT"}
        return {"status":"PERFORMANCE_EVIDENCE","evidence_modality":"AUDIO_COMPREHENSION"}

def goal_relation(evidence_modality, goal_modality, task_contract, policy):
    if evidence_modality not in EVIDENCE_MODALITIES:
        raise ModalityContractError("invalid evidence modality")
    if goal_modality not in GOAL_MODALITIES:
        raise ModalityContractError("invalid goal modality")

    # Contextual override first.
    if (
        evidence_modality=="TEXT_PRODUCTION"
        and task_contract=="EXPLICIT_WRITING_TASK"
        and goal_modality=="WRITING"
    ):
        return "DIRECT_TARGET_LEVEL"

    return policy["goal_relevance_matrix"][evidence_modality][goal_modality]

def allowed_measurement_dimensions(evidence_modality, runtime):
    base={
        "TEXT_PRODUCTION":{
            "recognition","guided_production","independent_production",
            "spontaneous_production","transfer","accuracy","pragmatic_control",
            "support_dependency"
        },
        "TEXT_COMPREHENSION":{
            "recognition","transfer","accuracy","support_dependency"
        },
        "VOICE_PRODUCTION":{
            "recognition","guided_production","independent_production",
            "spontaneous_production","transfer","accuracy","pragmatic_control",
            "support_dependency","speaking_fluency","pronunciation"
        },
        "AUDIO_COMPREHENSION":{
            "recognition","transfer","accuracy","support_dependency","listening_comprehension"
        }
    }[evidence_modality].copy()

    if evidence_modality=="VOICE_PRODUCTION":
        if not runtime.get("speaking_fluency_evaluator",False):
            base.discard("speaking_fluency")
        if not runtime.get("pronunciation_evaluator",False):
            base.discard("pronunciation")
    if evidence_modality=="AUDIO_COMPREHENSION":
        if not runtime.get("listening_comprehension_evaluator",False):
            base.discard("listening_comprehension")
    return sorted(base)

def can_claim(claim_kind, evidence_modalities, runtime, validated_assessment_module=False):
    em=set(evidence_modalities)
    if claim_kind=="TYPED_CONVERSATIONAL_CONTROL":
        return "TEXT_PRODUCTION" in em
    if claim_kind=="TARGET_LEVEL_TEXT_COMPREHENSION":
        return "TEXT_COMPREHENSION" in em
    if claim_kind=="SPEAKING_FLUENCY":
        return (
            "VOICE_PRODUCTION" in em
            and runtime.get("speaking_fluency_evaluator",False)
        )
    if claim_kind=="PRONUNCIATION":
        return (
            "VOICE_PRODUCTION" in em
            and runtime.get("pronunciation_evaluator",False)
        )
    if claim_kind=="LISTENING_COMPREHENSION":
        return (
            "AUDIO_COMPREHENSION" in em
            and runtime.get("listening_comprehension_evaluator",False)
        )
    if claim_kind=="IELTS_SPEAKING_BAND_PREDICTION":
        return bool(validated_assessment_module and "VOICE_PRODUCTION" in em)
    if claim_kind in {"SPEAKING_MASTERY","LISTENING_MASTERY"}:
        return False
    raise ModalityContractError("unknown claim kind")

def coverage_obligation(goal_modality, runtime):
    if goal_modality=="SPEAKING" and not runtime.get("voice_input",False):
        return {
            "direct_obligation":"UNAVAILABLE_IN_CURRENT_RUNTIME",
            "accrue_direct_coverage_debt":False,
            "preparatory_training_allowed":True
        }
    if goal_modality=="LISTENING" and not runtime.get("listening_comprehension_evaluator",False):
        return {
            "direct_obligation":"UNAVAILABLE_IN_CURRENT_RUNTIME",
            "accrue_direct_coverage_debt":False,
            "preparatory_training_allowed":True
        }
    return {
        "direct_obligation":"AVAILABLE",
        "accrue_direct_coverage_debt":True,
        "preparatory_training_allowed":True
    }

def canonical_state_key(target_type,target_id,evidence_modality):
    if evidence_modality not in EVIDENCE_MODALITIES:
        raise ModalityContractError("invalid evidence modality")
    return (target_type,target_id,evidence_modality)
