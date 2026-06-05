import pandas as pd
import datetime as dt
import numpy as np
import plotly.graph_objects as go
import plotly.colors as pc


def to_list(f_input):
    """
    Convert a string into a list
    return f_input if f_input is a list
    else raise ValueError

    :param f_input:
    :return: list
    """
    if isinstance(f_input, (str, int, float)):
        return [f_input]
    elif isinstance(f_input, list):
        return f_input
    else:
        raise ValueError(
            f"{f_input} must be an instance of str, int, float or list."
            f"Got {type(f_input)} instead"
        )


def select_in_list(target_list: list, target: str | list):
    """
    Select elements from a list based on a target string or a list of target strings.

    :param target_list: The source list from which elements will be selected.
    :param target: A string or a list of strings to match against elements in
    the target_list. If "*", all elements in the target_list are returned.

    :return: A list containing the selected elements from the target_list.
    """
    select_by_list = to_list(target)

    if target == "*":
        return target_list

    output_list = []
    for elmt in select_by_list:
        for items in target_list:
            if elmt in items:
                output_list.append(items)

    return output_list


def hourly_lst_from_dict(hourly_dict):
    if list(hourly_dict.keys())[-1] != 24:
        raise ValueError("Last dict key must be 24")

    val_list = []
    for hour, val in hourly_dict.items():
        val_list += [val for _ in range(len(val_list), hour)]

    return val_list


def is_items_in_list(items: str | list, target_list: list):
    """
    This function checks whether one or more items (strings or lists) are present
    within the target list.

    :param target_list: The list to search for items.
    :param items: The item(s) to check for presence in the target list. This can be a
    single string or a list of strings.
    :return: A list of Boolean values indicating whether each item is present in the
    target list.
    """
    items = to_list(items)
    return [True if elmt in target_list else False for elmt in items]


class Scheduler:
    def __init__(self, name, year=None):
        self.name = name
        if year is None:
            year = dt.datetime.today().year
        self.year = year
        self.series = pd.Series(
            index=pd.date_range(f"{year}-01-01 00:00:00", freq="h", periods=8760),
            name=name,
            dtype="float64",
        )

    def add_day_in_period(self, start, end, days, hourly_dict):
        start = dt.datetime.strptime(start, "%Y-%m-%d")
        end = dt.datetime.strptime(end, "%Y-%m-%d")
        end = end.replace(hour=23)

        if start.year != self.year or end.year != end.year:
            raise ValueError("start date or end date is out of bound ")

        day_list = to_list(days)
        period = self.series.loc[start:end]

        selected_timestamp = [idx for idx in period.index if idx.day_name() in day_list]

        self.series.loc[selected_timestamp] = hourly_lst_from_dict(hourly_dict) * int(
            len(selected_timestamp) / 24
        )


ZONE_PALETTE = (
    pc.qualitative.Safe
    + pc.qualitative.Set3
)
ADIABATIC_COLOR = "coral"
UNCONDITIONED_COLOR = "#9ECAE1"
WINDOW_COLOR = "cyan"
SHADING_COLOR = "mediumpurple"
CONDITIONED_ZONE_PALETTE = [
    "#67000d",
    "#a50f15",
    "#cb181d",
    "#ef3b2c",
    "#fb6a4a",
    "#fc9272",
    "#fcbba1",
]

def plot_idf_geometry(
    building,
    show_building_surfaces=True,
    show_fenestration_surfaces=True,
    show_shading_surfaces=True,
    show_names=False,
    opacity=0.7,
    color_mode="surface_type",
):
    """
        Interactive 3D visualization of an EnergyPlus building geometry.

        This function displays the geometry contained in an IDF model using
        Plotly. Building surfaces, fenestration surfaces and shading surfaces
        can be visualized independently. The resulting figure can be explored
        interactively (rotation, zoom, pan).

        Parameters
        ----------
        building : Building
            EnergyTool Building object containing an IDF model.

        show_building_surfaces : bool, default=True
            Display BuildingSurface:Detailed objects.

        show_fenestration_surfaces : bool, default=True
            Display FenestrationSurface:Detailed objects.

        show_shading_surfaces : bool, default=True
            Display Shading:Zone:Detailed objects.

        show_names : bool, default=False
            Display labels on the geometry.

            - In ``surface_type`` mode, surface names are displayed.
            - In ``zone`` mode, thermal zone names are displayed at the
              centroid of each zone.

        opacity : float, default=0.7
            Surface opacity between 0 and 1.

        color_mode : {"surface_type", "zone"}, default="surface_type"
            Controls how surfaces are colored.

            ``surface_type``:
                - External walls: light grey
                - Internal walls: khaki
                - Roofs: dark grey
                - Floors: grey
                - Windows: cyan
                - Shading surfaces: purple

            ``zone``:
                Colors are assigned according to thermal zone type.

                - Conditioned zones: red color palette
                - Adiabatic zones: orange/coral
                - Unconditioned zones: blue

        Returns
        -------
        plotly.graph_objects.Figure
            Interactive Plotly figure.

        Notes
        -----
        This function is intended for model inspection and debugging.

        Typical use cases include:

        - Checking generated geometry
        - Verifying window locations
        - Validating shading modifiers
          (overhangs, side fins, vegetation, PV systems, etc.)
        - Visualizing thermal zoning
        - Inspecting adiabatic and conditioned zones

        Examples
        --------
        Display the complete building geometry:

        >>> plot_idf_geometry(building).show()

        Display thermal zones:

        >>> plot_idf_geometry(
        ...     building,
        ...     color_mode="zone",
        ...     show_names=True,
        ... ).show()

        Display only windows and shading devices:

        >>> plot_idf_geometry(
        ...     building,
        ...     show_building_surfaces=False,
        ... ).show()

        Visualize the effect of a shading modifier:

        >>> set_shading_geometry(
        ...     building,
        ...     shading_type="overhang",
        ...     description={"Depth": 1.0},
        ... )
        >>>
        >>> plot_idf_geometry(building).show()
        """

    fig = go.Figure()

    groups = {}
    _label_traces = []

    def get_vertices(surface):
        n_vertices = int(surface.Number_of_Vertices)

        return np.array(
            [
                [
                    float(getattr(surface, f"Vertex_{i}_Xcoordinate")),
                    float(getattr(surface, f"Vertex_{i}_Ycoordinate")),
                    float(getattr(surface, f"Vertex_{i}_Zcoordinate")),
                ]
                for i in range(1, n_vertices + 1)
            ]
        )

    def _ensure_group(key, display_name, color):
        if key not in groups:
            groups[key] = dict(
                name=display_name,
                color=color,
                x=[], y=[], z=[],
                i=[], j=[], k=[],
                text=[],
                outlines=[],
            )
        return groups[key]

    def add_surface(vertices, group_key, display_name, color, name=None):
        if len(vertices) < 3:
            return

        group = _ensure_group(group_key, display_name, color)
        offset = len(group["x"])
        group["x"].extend(vertices[:, 0].tolist())
        group["y"].extend(vertices[:, 1].tolist())
        group["z"].extend(vertices[:, 2].tolist())
        group["text"].extend([name or ""] * len(vertices))

        for idx in range(1, len(vertices) - 1):
            group["i"].append(offset)
            group["j"].append(offset + idx)
            group["k"].append(offset + idx + 1)

        vertices_closed = np.vstack([vertices, vertices[0]])
        group["outlines"].append(
            go.Scatter3d(
                x=vertices_closed[:, 0],
                y=vertices_closed[:, 1],
                z=vertices_closed[:, 2],
                mode="lines",
                line=dict(color="black", width=2),
                showlegend=False,
                legendgroup=group_key,
                hoverinfo="skip",
            )
        )

        if show_names and color_mode != "zone":
            centroid = vertices.mean(axis=0)
            _label_traces.append(
                go.Scatter3d(
                    x=[centroid[0]],
                    y=[centroid[1]],
                    z=[centroid[2]],
                    mode="text",
                    text=[name],
                    showlegend=False,
                )
            )

    def add_zone_labels(building):

        zone_vertices = {}

        for surface in building.idf.idfobjects[
            "BUILDINGSURFACE:DETAILED"
        ]:

            zone = getattr(surface, "Zone_Name", None)

            if not zone:
                continue

            vertices = get_vertices(surface)

            zone_vertices.setdefault(zone, []).append(
                vertices
            )

        for zone, surfaces in zone_vertices.items():
            all_vertices = np.vstack(surfaces)

            centroid = all_vertices.mean(axis=0)
            centroid[2] += 0.5
            fig.add_trace(
                go.Scatter3d(
                    x=[centroid[0]],
                    y=[centroid[1]],
                    z=[centroid[2]],
                    mode="text",
                    text=[zone],
                    showlegend=False,
                )
            )

    def get_zone_types(building):

        zone_types = {}

        for zone in building.idf.idfobjects["ZONE"]:
            zone_types[zone.Name] = "unconditioned"

        for thermostat in building.idf.idfobjects.get(
                "ZONECONTROL:THERMOSTAT",
                []
        ):
            zone_types[
                thermostat.Zone_or_ZoneList_Name
            ] = "conditioned"

        for surface in building.idf.idfobjects[
            "BUILDINGSURFACE:DETAILED"
        ]:

            zone = getattr(surface, "Zone_Name", None)

            if not zone:
                continue

            boundary = getattr(
                surface,
                "Outside_Boundary_Condition",
                "",
            ).upper()

            if boundary == "ADIABATIC":
                zone_types[zone] = "adiabatic"

        return zone_types

    def get_zone_colors(building):

        zone_types = get_zone_types(building)

        zones = sorted(
            {
                surface.Zone_Name
                for surface in building.idf.idfobjects[
                "BUILDINGSURFACE:DETAILED"
            ]
                if getattr(surface, "Zone_Name", None)
            }
        )

        colors = {}

        idx = 0

        for zone in zones:

            if zone_types.get(zone) == "adiabatic":
                colors[zone] = ADIABATIC_COLOR

            else:
                zone_type = zone_types.get(
                    zone,
                    "conditioned"
                )

                if zone_type == "adiabatic":

                    colors[zone] = ADIABATIC_COLOR

                elif zone_type == "unconditioned":

                    colors[zone] = UNCONDITIONED_COLOR

                else:

                    colors[zone] = (
                        CONDITIONED_ZONE_PALETTE[
                            idx % len(
                                CONDITIONED_ZONE_PALETTE
                            )
                            ]
                    )

                    idx += 1

        return colors

    zone_types = get_zone_types(building)
    zone_colors = get_zone_colors(building)

    def get_building_surface_group(surface):
        if color_mode == "zone":
            zone_name = getattr(surface, "Zone_Name", None) or "unknown"
            z_type = zone_types.get(zone_name, "unconditioned")
            label = zone_name + (" (adiabatic)" if z_type == "adiabatic" else "")
            return zone_name, label, zone_colors.get(zone_name, "lightgray")
        stype = surface.Surface_Type.upper()
        boundary = getattr(surface, "Outside_Boundary_Condition", "").upper()
        if stype == "WALL":
            if boundary == "OUTDOORS":
                return "ext_wall", "External walls", "lightgray"
            return "int_wall", "Internal walls", "khaki"
        if stype == "ROOF":
            return "roof", "Roofs", "dimgray"
        if stype == "FLOOR":
            return "floor", "Floors", "gray"
        if stype == "CEILING":
            return "ceiling", "Ceilings", "silver"
        return "other", "Other", "lightgray"

    if show_building_surfaces:
        for surface in building.idf.idfobjects["BUILDINGSURFACE:DETAILED"]:
            key, label, color = get_building_surface_group(surface)
            add_surface(get_vertices(surface), key, label, color, surface.Name)

    if show_fenestration_surfaces:
        for surface in building.idf.idfobjects["FENESTRATIONSURFACE:DETAILED"]:
            add_surface(
                get_vertices(surface), "fenestration", "Windows", WINDOW_COLOR, surface.Name,
            )

    if show_shading_surfaces:
        for surface in building.idf.idfobjects["SHADING:ZONE:DETAILED"]:
            add_surface(
                get_vertices(surface), "shading", "Shading", SHADING_COLOR, surface.Name,
            )

    for key, group in groups.items():
        fig.add_trace(
            go.Mesh3d(
                x=group["x"],
                y=group["y"],
                z=group["z"],
                i=group["i"],
                j=group["j"],
                k=group["k"],
                color=group["color"],
                opacity=opacity,
                text=group["text"],
                hoverinfo="text",
                showscale=False,
                name=group["name"],
                legendgroup=key,
                showlegend=True,
            )
        )
        for outline in group["outlines"]:
            fig.add_trace(outline)

    for trace in _label_traces:
        fig.add_trace(trace)

    if show_names and color_mode == "zone":
        add_zone_labels(building)

    fig.update_layout(
        scene=dict(
            aspectmode="data",
            xaxis_title="X",
            yaxis_title="Y",
            zaxis_title="Z",
        ),
        height=900,
        margin=dict(l=0, r=0, b=0, t=20),
    )

    fig.update_layout(
        legend=dict(yanchor="top", y=1, xanchor="left", x=1.02)
    )

    return fig
