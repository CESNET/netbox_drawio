import django_tables2 as tables
from netbox.tables import NetBoxTable, columns

from netbox_drawio.models import Diagram, DiagramAssignment

PREVIEW_COLUMN = """
{% if record.svg_size %}
<a href="{{ record.get_absolute_url }}">
    <img src="{% url 'plugins:netbox_drawio:diagram_svg' pk=record.pk %}"
         style="max-height: 48px; max-width: 120px;" loading="lazy" alt="{{ record.name }}">
</a>
{% else %}
<span class="text-muted">&mdash;</span>
{% endif %}
"""

DIAGRAM_EXTRA_BUTTONS = """
{% if perms.netbox_drawio.change_diagram %}
<a href="{% url 'plugins:netbox_drawio:diagram_editor' pk=record.pk %}?return_url={{ request.get_full_path|urlencode }}"
   class="btn btn-sm btn-warning" title="Open editor">
  <i class="mdi mdi-pencil-ruler"></i>
</a>
{% endif %}
{% if perms.netbox_drawio.add_diagramassignment %}
<a href="{% url 'plugins:netbox_drawio:diagram_link' %}?diagram={{ record.pk }}&return_url={{ request.get_full_path|urlencode }}"
   class="btn btn-sm btn-success" title="Assign to object">
  <i class="mdi mdi-link-variant"></i>
</a>
{% endif %}
"""

PARENT_COLUMN = """
{% load helpers %}
{% with assignments=record.assignments.all %}
    {% if not assignments %}
        <span class="text-muted">&mdash;</span>
    {% elif assignments|length == 1 %}
        {% with a=assignments|first %}
            {% if a.parent %}
                {{ a.parent|linkify }}
            {% else %}
                <span class="text-muted">{{ a.object_type.app_label }} &gt; {{ a.object_type.model }} #{{ a.object_id }}</span>
            {% endif %}
        {% endwith %}
    {% else %}
        {% for a in assignments %}
            {% if forloop.counter <= 3 %}
                {% if a.parent %}{{ a.parent|linkify }}{% else %}<span class="text-muted">{{ a.object_type.app_label }} &gt; {{ a.object_type.model }} #{{ a.object_id }}</span>{% endif %}{% if not forloop.last and forloop.counter < 3 %}, {% endif %}
            {% endif %}
        {% endfor %}
        {% if assignments|length > 3 %}
            <span class="badge bg-secondary text-white">+{{ assignments|length|add:"-3" }} more</span>
        {% endif %}
    {% endif %}
{% endwith %}
"""

ASSIGNMENT_PARENT_COLUMN = """
{% if record.parent %}
    <a href="{{ record.parent.get_absolute_url }}">{{ record.parent }}</a>
{% else %}
    <span class="text-muted">{{ record.object_type.app_label }} &gt; {{ record.object_type.model }} #{{ record.object_id }}</span>
{% endif %}
"""


class DiagramTable(NetBoxTable):
    preview = tables.TemplateColumn(
        template_code=PREVIEW_COLUMN,
        verbose_name="Preview",
        orderable=False,
    )
    name = tables.Column(linkify=True)
    parent = tables.TemplateColumn(
        template_code=PARENT_COLUMN,
        verbose_name="Assigned To",
        orderable=False,
    )
    assignment_count = tables.Column(verbose_name="Assignments")
    owner = tables.Column(verbose_name="Owner", linkify=True)
    owner_group = tables.Column(accessor="owner__group", verbose_name="Owner Group", linkify=True)
    tags = columns.TagColumn(url_name="plugins:netbox_drawio:diagram_list")
    actions = columns.ActionsColumn(extra_buttons=DIAGRAM_EXTRA_BUTTONS)

    class Meta(NetBoxTable.Meta):
        model = Diagram
        fields = (
            "pk",
            "id",
            "preview",
            "name",
            "description",
            "parent",
            "assignment_count",
            "owner",
            "owner_group",
            "comments",
            "created",
            "last_updated",
            "tags",
            "actions",
        )
        default_columns = (
            "preview",
            "name",
            "description",
            "parent",
            "tags",
        )


class DiagramAssignmentTable(NetBoxTable):
    diagram = tables.Column(linkify=True, verbose_name="Diagram")
    object_type = columns.ContentTypeColumn(verbose_name="Object Type")
    parent = tables.TemplateColumn(
        template_code=ASSIGNMENT_PARENT_COLUMN,
        verbose_name="Object",
        orderable=False,
    )
    description = tables.Column(accessor="diagram__description", verbose_name="Description", orderable=False)
    tags = columns.TagColumn(url_name="plugins:netbox_drawio:diagramassignment_list")

    class Meta(NetBoxTable.Meta):
        model = DiagramAssignment
        fields = (
            "pk",
            "id",
            "diagram",
            "object_type",
            "parent",
            "description",
            "tags",
            "created",
            "actions",
        )
        default_columns = (
            "id",
            "diagram",
            "object_type",
            "parent",
            "tags",
            "created",
            "actions",
        )
