import os
import sys
import re
import contextlib

from Qt import QtGui

from openpype.client import (
    get_asset_by_name,
    get_subset_by_name,
    get_last_version_by_subset_id,
    get_representation_by_id,
    get_representation_by_name,
    get_representation_parents,
)
from openpype.pipeline import (
    switch_container,
    legacy_io,
)
from openpype.pipeline.context_tools import get_current_project_asset

from .pipeline import get_current_comp, comp_lock_and_undo_chunk

self = sys.modules[__name__]
self._project = None


def update_frame_range(start, end, comp=None, set_render_range=True,
                       handle_start=0, handle_end=0):
    """Set Fusion comp's start and end frame range

    Args:
        start (float, int): start frame
        end (float, int): end frame
        comp (object, Optional): comp object from fusion
        set_render_range (bool, Optional): When True this will also set the
            composition's render start and end frame.
        handle_start (float, int, Optional): frame handles before start frame
        handle_end (float, int, Optional): frame handles after end frame

    Returns:
        None

    """

    if not comp:
        comp = get_current_comp()

    # Convert any potential none type to zero
    handle_start = handle_start or 0
    handle_end = handle_end or 0

    attrs = {
        "COMPN_GlobalStart": start - handle_start,
        "COMPN_GlobalEnd": end + handle_end
    }

    # set frame range
    if set_render_range:
        attrs.update({
            "COMPN_RenderStart": start,
            "COMPN_RenderEnd": end
        })

    with comp_lock_and_undo_chunk(comp):
        comp.SetAttrs(attrs)


def set_asset_framerange():
    asset_doc = get_current_project_asset()
    start = asset_doc["data"]["frameStart"]
    end = asset_doc["data"]["frameEnd"]
    handle_start = asset_doc["data"]["handleStart"]
    handle_end = asset_doc["data"]["handleEnd"]
    update_frame_range(start, end, set_render_range=True,
                       handle_start=handle_start,
                       handle_end=handle_end)


def set_asset_resolution():
    """Set Comp's defaults"""
    asset_doc = get_current_project_asset()
    width = asset_doc["data"]["resolutionWidth"]
    height = asset_doc["data"]["resolutionHeight"]
    comp = get_current_comp()

    print("Setting comp frame format resolution to {}x{}".format(width,
                                                                 height))
    comp.SetPrefs({
        "Comp.FrameFormat.Width": width,
        "Comp.FrameFormat.Height": height,
    })


def get_additional_data(container):
    """Get Fusion related data for the container

    Args:
        container(dict): the container found by the ls() function

    Returns:
        dict
    """

    tool = container["_tool"]
    tile_color = tool.TileColor
    if tile_color is None:
        return {}

    return {"color": QtGui.QColor.fromRgbF(tile_color["R"],
                                           tile_color["G"],
                                           tile_color["B"])}


def switch_item(container,
                asset_name=None,
                subset_name=None,
                representation_name=None):
    """Switch container asset, subset or representation of a container by name.

    It'll always switch to the latest version - of course a different
    approach could be implemented.

    Args:
        container (dict): data of the item to switch with
        asset_name (str): name of the asset
        subset_name (str): name of the subset
        representation_name (str): name of the representation

    Returns:
        dict

    """

    if all(not x for x in [asset_name, subset_name, representation_name]):
        raise ValueError("Must have at least one change provided to switch.")

    # Collect any of current asset, subset and representation if not provided
    #   so we can use the original name from those.
    project_name = legacy_io.active_project()
    if any(not x for x in [asset_name, subset_name, representation_name]):
        repre_id = container["representation"]
        representation = get_representation_by_id(project_name, repre_id)
        repre_parent_docs = get_representation_parents(representation)
        if repre_parent_docs:
            version, subset, asset, _ = repre_parent_docs
        else:
            version = subset = asset = None

        if asset_name is None:
            asset_name = asset["name"]

        if subset_name is None:
            subset_name = subset["name"]

        if representation_name is None:
            representation_name = representation["name"]

    # Find the new one
    asset = get_asset_by_name(project_name, asset_name, fields=["_id"])
    assert asset, ("Could not find asset in the database with the name "
                   "'%s'" % asset_name)

    subset = get_subset_by_name(
        project_name, subset_name, asset["_id"], fields=["_id"]
    )
    assert subset, ("Could not find subset in the database with the name "
                    "'%s'" % subset_name)

    version = get_last_version_by_subset_id(
        project_name, subset["_id"], fields=["_id"]
    )
    assert version, "Could not find a version for {}.{}".format(
        asset_name, subset_name
    )

    representation = get_representation_by_name(
        project_name, representation_name, version["_id"]
    )
    assert representation, ("Could not find representation in the database "
                            "with the name '%s'" % representation_name)

    switch_container(container, representation)

    return representation


@contextlib.contextmanager
def maintained_selection():
    comp = get_current_comp()
    previous_selection = comp.GetToolList(True).values()
    try:
        yield
    finally:
        flow = comp.CurrentFrame.FlowView
        flow.Select()  # No args equals clearing selection
        if previous_selection:
            for tool in previous_selection:
                flow.Select(tool, True)


def get_frame_path(path):
    """Get filename for the Fusion Saver with padded number as '#'

    >>> get_frame_path("C:/test.exr")
    ('C:/test', 4, '.exr')

    >>> get_frame_path("filename.00.tif")
    ('filename.', 2, '.tif')

    >>> get_frame_path("foobar35.tif")
    ('foobar', 2, '.tif')

    Args:
        path (str): The path to render to.

    Returns:
        tuple: head, padding, tail (extension)

    """
    filename, ext = os.path.splitext(path)

    # Find a final number group
    match = re.match('.*?([0-9]+)$', filename)
    if match:
        padding = len(match.group(1))
        # remove number from end since fusion
        # will swap it with the frame number
        filename = filename[:-padding]
    else:
        padding = 4  # default Fusion padding

    return filename, padding, ext
