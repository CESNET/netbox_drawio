from netbox.plugins import PluginMenu, PluginMenuButton, PluginMenuItem

menu = PluginMenu(
    label="Draw.io",
    icon_class="mdi mdi-drawing",
    groups=(
        (
            "Diagrams",
            (
                PluginMenuItem(
                    link="plugins:netbox_drawio:diagram_list",
                    link_text="Diagrams",
                    permissions=["netbox_drawio.view_diagram"],
                    buttons=(
                        PluginMenuButton(
                            link="plugins:netbox_drawio:diagram_add",
                            title="Add",
                            icon_class="mdi mdi-plus-thick",
                            permissions=["netbox_drawio.add_diagram"],
                        ),
                    ),
                ),
                PluginMenuItem(
                    link="plugins:netbox_drawio:diagramassignment_list",
                    link_text="Assignments",
                    permissions=["netbox_drawio.view_diagramassignment"],
                ),
            ),
        ),
    ),
)
