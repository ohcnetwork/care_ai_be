from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PatientContext:
    """Bound at request time. Tools read ids from here; the LLM cannot supply them."""

    patient_id: UUID
    current_encounter_id: UUID
