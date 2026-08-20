import hashlib
import logging
from functools import cached_property

from core.models.object_types import ObjectType
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.urls import reverse
from netbox.models import NetBoxModel, PrimaryModel
from utilities.querysets import RestrictedQuerySet

logger = logging.getLogger(__name__)

# Blob fields kept out of change-log snapshots (see Diagram.serialize_object)
CHANGELOG_EXCLUDED_FIELDS = ("source_xml", "svg_cache")


class Diagram(PrimaryModel):
    """
    A draw.io diagram which may be assigned to any number of NetBox objects.
    """

    name = models.CharField(max_length=200)
    source_xml = models.TextField(
        blank=True,
        default="",
        verbose_name="Source XML",
        help_text="draw.io diagram source (mxfile XML)",
    )
    svg_cache = models.TextField(
        blank=True,
        default="",
        editable=False,
        verbose_name="SVG cache",
        help_text="Cached SVG export used for previews",
    )
    content_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        editable=False,
        help_text="SHA-256 over the diagram source and cached SVG; stands in for the excluded blobs in the change log",
    )

    clone_fields = ("description",)

    class Meta:
        ordering = ("name", "pk")  # name may be non-unique
        verbose_name = "Diagram"
        verbose_name_plural = "Diagrams"
        indexes = [
            models.Index(fields=["name", "id"], name="netbox_drawio_diagram_name_idx"),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_drawio:diagram", args=[self.pk])

    def serialize_object(self, exclude=None):
        # Keep the multi-hundred-KB XML/SVG blobs out of ObjectChange pre/post-change
        # snapshots; metadata changes remain fully change-logged. content_hash stays
        # included so content-only saves still produce a change record.
        return super().serialize_object(exclude=[*(exclude or []), *CHANGELOG_EXCLUDED_FIELDS])

    def save(self, *args, **kwargs):
        # Skip re-hashing only when every blob field is deferred and therefore
        # untouched (assignment removes a field from the deferred set). If any
        # blob is loaded it may have changed, so recompute — even though that
        # fetches back a still-deferred sibling.
        if not self.get_deferred_fields().issuperset(CHANGELOG_EXCLUDED_FIELDS):
            self.content_hash = self._compute_content_hash()
        super().save(*args, **kwargs)

    def _compute_content_hash(self):
        # Both blobs feed the hash: it doubles as the SVG endpoint's ETag, so an
        # SVG-only update must produce a new value. NUL separator prevents
        # xml/svg boundary ambiguity (neither field can contain NUL).
        if not (self.source_xml or self.svg_cache):
            return ""
        hasher = hashlib.sha256(self.source_xml.encode("utf-8"))
        hasher.update(b"\x00")
        hasher.update(self.svg_cache.encode("utf-8"))
        return hasher.hexdigest()


class DiagramAssignment(NetBoxModel):
    """
    A link between a Diagram and a NetBox object.
    """

    diagram = models.ForeignKey(
        to=Diagram,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    object_type = models.ForeignKey(
        to=ObjectType,
        on_delete=models.CASCADE,
    )
    object_id = models.PositiveBigIntegerField()

    objects = RestrictedQuerySet.as_manager()

    class Meta:
        ordering = ("diagram", "object_type", "object_id")
        verbose_name = "Diagram Assignment"
        verbose_name_plural = "Diagram Assignments"
        constraints = [
            models.UniqueConstraint(
                fields=("diagram", "object_type", "object_id"),
                name="netbox_drawio_unique_assignment",
            )
        ]
        indexes = [
            models.Index(fields=["object_type", "object_id"], name="netbox_drawio_assign_ot_id_idx"),
        ]

    def __str__(self):
        return f"{self.diagram} → {self.object_type} #{self.object_id}"

    @cached_property
    def parent(self):
        # Cached: table columns render this several times per row
        if not (self.object_type_id and self.object_id):
            return None

        if self.object_type.model_class() is None:
            # Model was probably deleted or uninstalled
            return None

        try:
            return self.object_type.get_object_for_this_type(id=self.object_id)
        except ObjectDoesNotExist:
            return None

    def get_absolute_url(self):
        return reverse("plugins:netbox_drawio:diagramassignment", args=[self.pk])
