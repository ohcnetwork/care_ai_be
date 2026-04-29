from rest_framework.exceptions import PermissionDenied

from care.security.authorization import AuthorizationController


def authorize_encounter_read(user, encounter) -> None:
    """Mirror EncounterViewSet.authorize_retrieve. Raises PermissionDenied on fail."""
    if AuthorizationController.call("can_view_patient_obj", user, encounter.patient):
        return
    if AuthorizationController.call("can_view_encounter_obj", user, encounter):
        return
    raise PermissionDenied("You do not have permission to view this encounter")
