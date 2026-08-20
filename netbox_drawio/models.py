import hashlib
import logging

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
        help_text="SHA-256 of the diagram source; stands in for the excluded blobs in the change log",
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
        self.content_hash = hashlib.sha256(self.source_xml.encode("utf-8")).hexdigest() if self.source_xml else ""
        super().save(*args, **kwargs)


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

    def get_display(self):
        """Rich display — only call when parent is prefetched or single-object context."""
        parent = self.parent
        if parent:
            return f"{self.diagram} → {parent}"
        return self.__str__()

    @property
    def parent(self):
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
