import logging

from agents import RunContextWrapper, function_tool

from care.emr.models import (
    AllergyIntolerance,
    Condition,
    Encounter,
    MedicationRequest,
    Observation,
    Patient,
    ServiceRequest,
)
from care.emr.resources.allergy_intolerance.spec import AllergyIntoleranceReadSpec
from care.emr.resources.condition.spec import ConditionReadSpec
from care.emr.resources.encounter.spec import EncounterListSpec, EncounterRetrieveSpec
from care.emr.resources.medication.request.spec import MedicationRequestReadSpec
from care.emr.resources.observation.spec import ObservationReadSpec
from care.emr.resources.patient.spec import PatientRetrieveSpec
from care.emr.resources.service_request.spec import ServiceRequestReadSpec

from care_ai.agent.context import PatientContext
from care_ai.agent.tool_helpers import now_minus, serialize_list
from care_ai.settings import plugin_settings

logger = logging.getLogger("care_ai.tools")


@function_tool
def get_patient_demographics(ctx: RunContextWrapper[PatientContext]) -> dict:
    """Return basic demographics (age, sex, blood group, identifiers) for the current patient."""
    try:
        patient = Patient.objects.get(external_id=ctx.context.patient_id)
        return PatientRetrieveSpec.serialize(patient).to_json()
    except Exception as exc:
        logger.exception("get_patient_demographics failed")
        return {"error": f"{type(exc).__name__}: {exc}"}


@function_tool
def get_current_encounter(ctx: RunContextWrapper[PatientContext]) -> dict:
    """Return details (class, status, period, priority, location, care team) of the current encounter."""
    try:
        encounter = Encounter.objects.get(external_id=ctx.context.current_encounter_id)
        return EncounterRetrieveSpec.serialize(encounter).to_json()
    except Exception as exc:
        logger.exception("get_current_encounter failed")
        return {"error": f"{type(exc).__name__}: {exc}"}


@function_tool
def get_active_allergies(ctx: RunContextWrapper[PatientContext]) -> dict:
    """List active AllergyIntolerance entries for the patient with criticality."""
    try:
        qs = AllergyIntolerance.objects.filter(
            patient__external_id=ctx.context.patient_id,
            clinical_status="active",
        ).order_by("-created_date")
        return serialize_list(AllergyIntoleranceReadSpec, qs, limit=200)
    except Exception as exc:
        logger.exception("get_active_allergies failed")
        return {"error": f"{type(exc).__name__}: {exc}"}


@function_tool
def get_active_conditions(ctx: RunContextWrapper[PatientContext]) -> dict:
    """List active Conditions (symptoms + diagnoses) for the patient with severity and onset."""
    try:
        qs = Condition.objects.filter(
            patient__external_id=ctx.context.patient_id,
            clinical_status="active",
        ).order_by("-created_date")
        return serialize_list(ConditionReadSpec, qs, limit=200)
    except Exception as exc:
        logger.exception("get_active_conditions failed")
        return {"error": f"{type(exc).__name__}: {exc}"}


@function_tool
def get_active_medications(ctx: RunContextWrapper[PatientContext]) -> dict:
    """List active medication requests for the patient."""
    try:
        qs = MedicationRequest.objects.filter(
            patient__external_id=ctx.context.patient_id,
            status="active",
        ).order_by("-created_date")
        return serialize_list(MedicationRequestReadSpec, qs, limit=200)
    except Exception as exc:
        logger.exception("get_active_medications failed")
        return {"error": f"{type(exc).__name__}: {exc}"}


@function_tool
def get_recent_observations(
    ctx: RunContextWrapper[PatientContext],
    hours: int = 24,
) -> dict:
    """List Observations (vitals, labs) recorded within the last `hours` (1-720, default 24)."""
    try:
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
    except Exception as exc:
        logger.exception("get_recent_observations failed")
        return {"error": f"{type(exc).__name__}: {exc}"}


@function_tool
def get_service_requests(ctx: RunContextWrapper[PatientContext]) -> dict:
    """List ServiceRequests on the current encounter."""
    try:
        qs = ServiceRequest.objects.filter(
            encounter__external_id=ctx.context.current_encounter_id,
        ).order_by("-created_date")
        return serialize_list(ServiceRequestReadSpec, qs, limit=200)
    except Exception as exc:
        logger.exception("get_service_requests failed")
        return {"error": f"{type(exc).__name__}: {exc}"}


@function_tool
def get_prior_encounters(
    ctx: RunContextWrapper[PatientContext],
    months: int = 12,
) -> dict:
    """List the patient's prior encounters within the last `months` (1-60, default 12), excluding the current one."""
    try:
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
    except Exception as exc:
        logger.exception("get_prior_encounters failed")
        return {"error": f"{type(exc).__name__}: {exc}"}


ALL_TOOLS = [
    get_patient_demographics,
    get_current_encounter,
    get_active_allergies,
    get_active_conditions,
    get_active_medications,
    get_recent_observations,
    get_service_requests,
    get_prior_encounters,
]
