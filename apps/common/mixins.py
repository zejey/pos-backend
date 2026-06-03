"""Reusable viewset mixins."""
from apps.accounts.services import log_activity


class ActivityLogMixin:
    """Log create/update/destroy on a ModelViewSet to the activity trail (FIX-07).

    The action name is derived from the model, e.g. ``CATEGORY_UPDATE``. A
    viewset that needs custom create logging can still override
    ``perform_create`` — this mixin then only adds update/destroy coverage.
    Set ``log_entity`` to override the entity label.
    """

    log_entity = None

    def _log_entity(self):
        return self.log_entity or self.get_queryset().model.__name__

    def _log(self, pk, verb):
        entity = self._log_entity()
        log_activity(
            self.request.user, f"{entity.upper()}_{verb}",
            entity=entity, entity_id=pk, request=self.request,
        )

    def perform_create(self, serializer):
        obj = serializer.save()
        self._log(obj.pk, "CREATE")

    def perform_update(self, serializer):
        obj = serializer.save()
        self._log(obj.pk, "UPDATE")

    def perform_destroy(self, instance):
        pk = instance.pk
        super().perform_destroy(instance)
        self._log(pk, "DELETE")
