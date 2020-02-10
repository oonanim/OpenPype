"""Create a model asset."""

import bpy

from avalon import api
from avalon.blender import Creator, lib


class CreateModel(Creator):
    """Polygonal static geometry"""

    name = "modelMain"
    label = "Model"
    family = "model"
    icon = "cube"

    def process(self):
        import pype.blender

        asset = self.data["asset"]
        subset = self.data["subset"]
        name = pype.blender.plugin.asset_name(asset, subset)
        collection = bpy.data.collections.new(name=name)
        bpy.context.scene.collection.children.link(collection)
        self.data['task'] = api.Session.get('AVALON_TASK')
        lib.imprint(collection, self.data)

        if (self.options or {}).get("useSelection"):
            for obj in lib.get_selection():
                collection.objects.link(obj)

        return collection
