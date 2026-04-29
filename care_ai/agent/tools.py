from agents import RunContextWrapper, function_tool

from care.emr.models.allergy_intolerance import AllergyIntolerance
from care.emr.models.condition import Condition
from care.emr.models.encounter import Encounter
from care.emr.models.medication_administration import MedicationAdministration
from care.emr.models.medication_request import MedicationRequest
from care.emr.models.observation import Observation
from care.emr.models.patient import Patient
from care.emr.models.questionnaire import QuestionnaireResponse
from care.emr.models.service_request import ServiceRequest
from care.emr.resources.allergy_intolerance.spec import AllergyIntoleranceReadSpec
from care.emr.resources.condition.spec import ConditionReadSpec
from care.emr.resources.encounter.spec import EncounterListSpec, EncounterRetrieveSpec
from care.emr.resources.medication.administration.spec import (
    MedicationAdministrationReadSpec,
)
from care.emr.resources.medication.request.spec import MedicationRequestReadSpec
from care.emr.resources.observation.spec import ObservationReadSpec
from care.emr.resources.patient.spec import PatientRetrieveSpec
from care.emr.resources.service_request.spec import ServiceRequestReadSpec

from care_ai.agent.context import PatientContext
from care_ai.agent.tool_helpers import now_minus, safe_tool, serialize_list
from care_ai.settings import plugin_settings


@function_tool
@safe_tool
def get_patient_demographics(ctx: RunContextWrapper[PatientContext]) -> dict:
    """Return basic demographics (age, sex, blood group, identifiers) for the current patient."""
    patient = Patient.objects.get(external_id=ctx.context.patient_id)
    return PatientRetrieveSpec.serialize(patient).to_json()


@function_tool
@safe_tool
def get_current_encounter(ctx: RunContextWrapper[PatientContext]) -> dict:
    """Return details (class, status, period, priority, location, care team) of the current encounter."""
    encounter = Encounter.objects.get(external_id=ctx.context.current_encounter_id)
    return EncounterRetrieveSpec.serialize(encounter).to_json()


@function_tool
@safe_tool
def get_active_allergies(ctx: RunContextWrapper[PatientContext]) -> dict:
    """List active AllergyIntolerance entries for the patient with criticality."""
    qs = AllergyIntolerance.objects.filter(
        patient__external_id=ctx.context.patient_id,
        clinical_status="active",
    ).order_by("-created_date")
    return serialize_list(AllergyIntoleranceReadSpec, qs, limit=200)


@function_tool
@safe_tool
def get_active_conditions(ctx: RunContextWrapper[PatientContext]) -> dict:
    """List active Conditions (symptoms + diagnoses) for the patient with severity and onset."""
    qs = Condition.objects.filter(
        patient__external_id=ctx.context.patient_id,
        clinical_status="active",
    ).order_by("-created_date")
    return serialize_list(ConditionReadSpec, qs, limit=200)


@function_tool
@safe_tool
def get_active_medications(ctx: RunContextWrapper[PatientContext]) -> dict:
    """List active medication requests for the patient."""
    qs = MedicationRequest.objects.filter(
        patient__external_id=ctx.context.patient_id,
        status="active",
    ).order_by("-created_date")
    return serialize_list(MedicationRequestReadSpec, qs, limit=200)


@function_tool
@safe_tool
def get_recent_observations(
    ctx: RunContextWrapper[PatientContext],
    hours: int = 24,
) -> dict:
    """List Observations (vitals, labs) recorded within the last `hours` (1-720, default 24)."""
    hours = max(1, min(720, hours))
    qs = Observation.objects.filter(
        patient__external_id=ctx.context.patient_id,
        effective_datetime__gte=now_minus(hours=hours),
    ).order_by("-effective_datetime")
    return serialize_list(
        ObservationReadSpec,
        qs,
        limit=plugin_settings.CARE_AI_OBSERVATION_ROW_LIMIT,
    )


@function_tool
@safe_tool
def get_service_requests(ctx: RunContextWrapper[PatientContext]) -> dict:
    """List ServiceRequests on the current encounter."""
    qs = ServiceRequest.objects.filter(
        encounter__external_id=ctx.context.current_encounter_id,
    ).order_by("-created_date")
    return serialize_list(ServiceRequestReadSpec, qs, limit=200)


@function_tool
@safe_tool
def get_prior_encounters(
    ctx: RunContextWrapper[PatientContext],
    months: int = 12,
) -> dict:
    """List the patient's prior encounters within the last `months` (1-60, default 12), excluding the current one."""
    months = max(1, min(60, months))
    qs = (
        Encounter.objects.filter(
            patient__external_id=ctx.context.patient_id,
            created_date__gte=now_minus(days=30 * months),
        )
        .exclude(external_id=ctx.context.current_encounter_id)
        .order_by("-created_date")
    )
    return serialize_list(
        EncounterListSpec,
        qs,
        limit=plugin_settings.CARE_AI_ENCOUNTER_ROW_LIMIT,
    )


@function_tool
@safe_tool
def get_medication_administrations(
    ctx: RunContextWrapper[PatientContext],
    hours: int = 72,
) -> dict:
    """List MedicationAdministration records (actual doses given) on the current encounter within the last `hours` (1-720, default 72).

    Distinct from get_active_medications, which lists prescriptions/orders.
    Useful for confirming what was actually administered, when, and by whom.
    """
    hours = max(1, min(720, hours))
    qs = MedicationAdministration.objects.filter(
        encounter__external_id=ctx.context.current_encounter_id,
        created_date__gte=now_minus(hours=hours),
    ).order_by("-created_date")
    return serialize_list(MedicationAdministrationReadSpec, qs, limit=200)


@function_tool
@safe_tool
def get_from_responses(
    ctx: RunContextWrapper[PatientContext],
    limit: int = 50,
) -> dict:
    """List submitted QuestionnaireResponse entries (forms) for the current encounter.

    Each item includes the questionnaire title/slug, status, who submitted it,
    when, and a list of question/answer pairs from `render_responses()`. Useful
    for computing scores (NEWS2, GCS, qSOFA, MEWS, pain scales) or pulling
    specific values out of structured forms.
    """
    limit = max(1, min(200, limit))
    qs = (
        QuestionnaireResponse.objects.select_related("questionnaire", "created_by")
        .filter(encounter__external_id=ctx.context.current_encounter_id)
        .order_by("-created_date")
    )
    rows = list(qs[: limit + 1])
    truncated = len(rows) > limit
    rows = rows[:limit]

    items = []
    for r in rows:
        q = r.questionnaire
        items.append(
            {
                "id": str(r.external_id),
                "questionnaire": {
                    "id": str(q.external_id) if q else None,
                    "slug": q.slug if q else None,
                    "title": q.title if q else None,
                },
                "status": r.status,
                "submitted_at": (
                    r.created_date.isoformat() if r.created_date else None
                ),
                "submitted_by": (
                    r.created_by.username if r.created_by_id else None
                ),
                "responses": r.render_responses(),
            }
        )
    return {"items": items, "count": len(items), "truncated": truncated}


ALL_TOOLS = [
    get_patient_demographics,
    get_current_encounter,
    get_active_allergies,
    get_active_conditions,
    get_active_medications,
    get_recent_observations,
    get_service_requests,
    get_prior_encounters,
    get_medication_administrations,
    get_from_responses,
]
