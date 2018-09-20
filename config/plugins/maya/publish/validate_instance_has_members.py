import pyblish.api
import config.api


class ValidateInstanceHasMembers(pyblish.api.InstancePlugin):
    """Validates instance objectSet has *any* members."""

    order = config.api.ValidateContentsOrder
    hosts = ["maya"]
    label = 'Instance has members'
    actions = [config.api.SelectInvalidAction]

    @classmethod
    def get_invalid(cls, instance):

        invalid = list()
        if not instance.data["setMembers"]:
            objectset_name = instance.data['name']
            invalid.append(objectset_name)

        return invalid

    def process(self, instance):

        invalid = self.get_invalid(instance)
        if invalid:
            raise RuntimeError("Empty instances found: {0}".format(invalid))
