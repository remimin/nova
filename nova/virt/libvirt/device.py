#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
import six

import nova.context
from nova import exception
from nova import objects


class Device(object):
    """The interface for managing the device"""

    def __init__(self, instance_uuid=None, flavor_id=None):
        self.instance_uuid = instance_uuid
        self.flavor_id = flavor_id

    def is_assigned(self):
        """Check the device is assigned or not"""
        return bool(self.instance_uuid)


class MDevDevice(Device):

    def __init__(self, uuid, type, parent, instance_uuid=None, flavor_id=None):
        super(MDevDevice, self).__init__(instance_uuid=instance_uuid,
                                         flavor_id=flavor_id)
        # The mediated device's uuid
        self.uuid = uuid
        # The mediated device's type
        self.type = type
        # The parent of mdev, which is referenced to the physical device.
        self.parent = parent

    def __str__(self):
        return 'MDevDevice(uuid=%(uuid)s, ' \
               'type=%(type)s, ' \
               'parent=%(parent)s, ' \
               'instance_uuid=%(instance_uuid)s, ' \
               'flavor_id=%(flavor_id)s)' % ({
                   'uuid': self.uuid,
                   'type': self.type,
                   'parent': self.parent,
                   'instance_uuid': self.instance_uuid,
                   'flavor_id': self.flavor_id,
               })


class DeviceManager(object):

    def __init__(self, driver):
        # The nova.virt.libvirt.driver.LibvirtDriver object.
        self.driver = driver
        self._mdev_list = []

    def initialize(self, supports_mdev):
        """Initialize the assignment status of devices.

        :param supports_mdev: The mediated device will be populated for True.
        """
        if supports_mdev:
            self._populate_existing_mdevs()

    def claim_for_instance(self, instance, allocations, flavor=None):
        """Claim the devices for the instance.

        :param instance: nova.objects.instance.Instance Object.
        :param allocations: The placement allocation records.
        :param flavor: nova.objects.flavor.Flavor Object.
        :raises: exception.ComputeResourcesUnavailable if the virt driver can't
            find out any available device.
        """
        self._claim_mdevs_for_instance(instance, allocations, flavor=flavor)

    def unclaim_for_instance(self, instance, flavor=None):
        """Unclaim the devices for the instance.

        :param instance: nova.objects.instance.Instance object.
        :param flavor: nova.objects.flavor.Flavor Object.
        """
        self._unclaim_mdevs_for_instance(instance, flavor=flavor)

    def _populate_existing_mdevs(self):
        """Populate all the existing mdevs, and its assignment."""
        requested_types = self.driver._get_supported_vgpu_types()
        if not requested_types:
            return

        # Actually, we only support one vgpu type now.
        existing_mdevs = self.driver._get_mediated_devices(
            requested_types[0])
        assigned_mdevs = self.driver._get_all_assigned_mediated_devices()

        # FIXME(alex_xu): When the instance is in the VERIFY_RESIZED status,
        # we should fetch the new flavor for this instance. This should be
        # fixed along with Bug #1778563.
        context = nova.context.get_admin_context()
        instances = objects.InstanceList.get_by_filters(context,
            {'uuid': list(assigned_mdevs.values())})
        instance_flavor_id_mapping = {
            instance.uuid: instance.instance_type_id
                for instance in instances}

        for mdev in existing_mdevs:
            instance_uuid = assigned_mdevs.get(mdev['uuid'], None)
            vgpu_dev = MDevDevice(
                mdev['uuid'], mdev['type'], mdev['parent'],
                instance_uuid=instance_uuid,
                flavor_id=instance_flavor_id_mapping.get(instance_uuid, None))
            self._mdev_list.append(vgpu_dev)

    def _claim_mdevs_for_instance(self, instance, allocations, flavor):
        # NOTE: Only get requested types and vgpus asked, because we don't have
        # resource provider tree currently.
        requested_types, vgpus_asked = (
            self.driver._get_requested_vgpus(allocations))

        if not vgpus_asked:
            return

        # NOTE: we get all non-assigned mdevs no matter their parents because
        # gpu policy will take effect inside create_new_mediated_device
        mdevs_available = [mdev for mdev in self._mdev_list
                           if not mdev.is_assigned() and
                           (not requested_types or
                            mdev.type == requested_types[0])]

        flavor_id = flavor.id if flavor else instance.instance_type_id
        chosen_mdevs = []
        for _ in six.moves.range(vgpus_asked):
            mdev = self.driver._create_new_mediated_device(
                requested_types, mdevs_available=mdevs_available)
            if mdev:
                mdev.instance_uuid = instance.uuid
                mdev.flavor_id = flavor_id
                # NOTE: if mdev is already in the _mdev_list, we should delete
                # the old one.
                for i, m in enumerate(self._mdev_list):
                    if m.uuid == mdev.uuid:
                        del self._mdev_list[i]
                        break
                self._mdev_list.append(mdev)
                chosen_mdevs.append(mdev)
            # There is no any available mdev, raise the exception and
            # rollback the assignment
            if not mdev:
                for mdev in chosen_mdevs:
                    mdev.instance_uuid = None
                raise exception.ComputeResourcesUnavailable(
                    reason="vGPU resource is not available")

    def _unclaim_mdevs_for_instance(self, instance, flavor):
        flavor_id = flavor.id if flavor else instance.instance_type_id
        for mdev in self._mdev_list:
            if (mdev.instance_uuid == instance.uuid and
                    mdev.flavor_id == flavor_id):
                mdev.instance_uuid = None

    def get_claimed_devices_for_instance(self, instance, flavor=None):
        return self._get_claimed_mdevs_for_instance(instance, flavor=flavor)

    def _get_claimed_mdevs_for_instance(self, instance, flavor=None):
        flavor_id = flavor.id if flavor else instance.instance_type_id
        return [mdev for mdev in self._mdev_list
            if mdev.instance_uuid == instance.uuid and
                (mdev.flavor_id == flavor_id)]

    def get_mdev_list(self):
        return self._mdev_list
