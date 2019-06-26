==================
Compute schedulers
==================

Compute uses the ``nova-scheduler`` service to determine how to dispatch
compute requests. For example, the ``nova-scheduler`` service determines on
which host a VM should launch.  In the context of filters, the term ``host``
means a physical node that has a ``nova-compute`` service running on it.  You
can configure the scheduler through a variety of options.

Compute is configured with the following default scheduler options in the
``/etc/nova/nova.conf`` file:

.. code-block:: ini

   [scheduler]
   driver = filter_scheduler

   [filter_scheduler]
   available_filters = nova.scheduler.filters.all_filters
   enabled_filters = AvailabilityZoneFilter, ComputeFilter, ComputeCapabilitiesFilter, ImagePropertiesFilter, ServerGroupAntiAffinityFilter, ServerGroupAffinityFilter

By default, the scheduler ``driver`` is configured as a filter scheduler, as
described in the next section. In the default configuration, this scheduler
considers hosts that meet all the following criteria:

* Are in the requested availability zone (``AvailabilityZoneFilter``).

* Can service the request (``ComputeFilter``).

* Satisfy the extra specs associated with the instance type
  (``ComputeCapabilitiesFilter``).

* Satisfy any architecture, hypervisor type, or virtual machine mode properties
  specified on the instance's image properties (``ImagePropertiesFilter``).

* Are on a different host than other instances of a group (if requested)
  (``ServerGroupAntiAffinityFilter``).

* Are in a set of group hosts (if requested) (``ServerGroupAffinityFilter``).

The scheduler chooses a new host when an instance is migrated.

When evacuating instances from a host, the scheduler service honors the target
host defined by the administrator on the :command:`nova evacuate` command.  If
a target is not defined by the administrator, the scheduler determines the
target host. For information about instance evacuation, see
:ref:`Evacuate instances <node-down-evacuate-instances>`.

.. _compute-scheduler-filters:

Prefiltering
~~~~~~~~~~~~

As of the Rocky release, the scheduling process includes a prefilter
step to increase the efficiency of subsequent stages. These prefilters
are largely optional, and serve to augment the request that is sent to
placement to reduce the set of candidate compute hosts based on
attributes that placement is able to answer for us ahead of time. In
addition to the prefilters listed here, also see `Tenant Isolation
with Placement`_ and `Availability Zones with Placement`_.

Compute Image Type Support
--------------------------

Starting in the Train release, there is a prefilter available for
excluding compute nodes that do not support the ``disk_format`` of the
image used in a boot request. This behavior is enabled by setting
:oslo.config:option:`[scheduler]/query_placement_for_image_type_support=True
<scheduler.query_placement_for_image_type_support>`. For
example, the libvirt driver, when using ceph as an ephemeral backend,
does not support ``qcow2`` images (without an expensive conversion
step). In this case (and especially if you have a mix of ceph and
non-ceph backed computes), enabling this feature will ensure that the
scheduler does not send requests to boot a ``qcow2`` image to computes
backed by ceph.

Filter scheduler
~~~~~~~~~~~~~~~~

The filter scheduler (``nova.scheduler.filter_scheduler.FilterScheduler``) is
the default scheduler for scheduling virtual machine instances.  It supports
filtering and weighting to make informed decisions on where a new instance
should be created.

When the filter scheduler receives a request for a resource, it first applies
filters to determine which hosts are eligible for consideration when
dispatching a resource. Filters are binary: either a host is accepted by the
filter, or it is rejected. Hosts that are accepted by the filter are then
processed by a different algorithm to decide which hosts to use for that
request, described in the :ref:`weights` section.

**Filtering**

.. figure:: /figures/filteringWorkflow1.png

The ``available_filters`` configuration option in ``nova.conf``
provides the Compute service with the list of the filters that are available
for use by the scheduler. The default setting specifies all of the filters that
are included with the Compute service:

.. code-block:: ini

   [filter_scheduler]
   available_filters = nova.scheduler.filters.all_filters

This configuration option can be specified multiple times.  For example, if you
implemented your own custom filter in Python called ``myfilter.MyFilter`` and
you wanted to use both the built-in filters and your custom filter, your
``nova.conf`` file would contain:

.. code-block:: ini

   [filter_scheduler]
   available_filters = nova.scheduler.filters.all_filters
   available_filters = myfilter.MyFilter

The :oslo.config:option:`filter_scheduler.enabled_filters` configuration option
in ``nova.conf`` defines the list of filters that are applied by the
``nova-scheduler`` service.

Compute filters
~~~~~~~~~~~~~~~

The following sections describe the available compute filters.

AggregateCoreFilter
-------------------

Filters host by CPU core numbers with a per-aggregate ``cpu_allocation_ratio``
value. If the per-aggregate value is not found, the value falls back to the
global setting.  If the host is in more than one aggregate and more than one
value is found, the minimum value will be used.  For information about how to
use this filter, see :ref:`host-aggregates`. See also :ref:`CoreFilter`.

Note the ``cpu_allocation_ratio`` :ref:`bug 1804125 <bug-1804125>` restriction.

AggregateDiskFilter
-------------------

Filters host by disk allocation with a per-aggregate ``disk_allocation_ratio``
value. If the per-aggregate value is not found, the value falls back to the
global setting.  If the host is in more than one aggregate and more than one
value is found, the minimum value will be used.  For information about how to
use this filter, see :ref:`host-aggregates`. See also :ref:`DiskFilter`.

Note the ``disk_allocation_ratio`` :ref:`bug 1804125 <bug-1804125>`
restriction.

AggregateImagePropertiesIsolation
---------------------------------

Matches properties defined in an image's metadata against those of aggregates
to determine host matches:

* If a host belongs to an aggregate and the aggregate defines one or more
  metadata that matches an image's properties, that host is a candidate to boot
  the image's instance.

* If a host does not belong to any aggregate, it can boot instances from all
  images.

For example, the following aggregate ``myWinAgg`` has the Windows operating
system as metadata (named 'windows'):

.. code-block:: console

   $ openstack aggregate show myWinAgg
   +-------------------+----------------------------+
   | Field             | Value                      |
   +-------------------+----------------------------+
   | availability_zone | zone1                      |
   | created_at        | 2017-01-01T15:36:44.000000 |
   | deleted           | False                      |
   | deleted_at        | None                       |
   | hosts             | [u'sf-devel']              |
   | id                | 1                          |
   | name              | myWinAgg                   |
   | properties        | os_distro='windows'        |
   | updated_at        | None                       |
   +-------------------+----------------------------+

In this example, because the following Win-2012 image has the ``windows``
property, it boots on the ``sf-devel`` host (all other filters being equal):

.. code-block:: console

   $ openstack image show Win-2012
   +------------------+------------------------------------------------------+
   | Field            | Value                                                |
   +------------------+------------------------------------------------------+
   | checksum         | ee1eca47dc88f4879d8a229cc70a07c6                     |
   | container_format | bare                                                 |
   | created_at       | 2016-12-13T09:30:30Z                                 |
   | disk_format      | qcow2                                                |
   | ...                                                                     |
   | name             | Win-2012                                             |
   | ...                                                                     |
   | properties       | os_distro='windows'                                  |
   | ...                                                                     |

You can configure the ``AggregateImagePropertiesIsolation`` filter by using the
following options in the ``nova.conf`` file:

.. code-block:: ini

   # Considers only keys matching the given namespace (string).
   # Multiple values can be given, as a comma-separated list.
   aggregate_image_properties_isolation_namespace = <None>

   # Separator used between the namespace and keys (string).
   aggregate_image_properties_isolation_separator = .

.. _AggregateInstanceExtraSpecsFilter:

AggregateInstanceExtraSpecsFilter
---------------------------------

Matches properties defined in extra specs for an instance type against
admin-defined properties on a host aggregate.  Works with specifications that
are scoped with ``aggregate_instance_extra_specs``.  Multiple values can be
given, as a comma-separated list.  For backward compatibility, also works with
non-scoped specifications; this action is highly discouraged because it
conflicts with :ref:`ComputeCapabilitiesFilter` filter when you enable both
filters.  For information about how to use this filter, see the
:ref:`host-aggregates` section.

AggregateIoOpsFilter
--------------------

Filters host by disk allocation with a per-aggregate ``max_io_ops_per_host``
value. If the per-aggregate value is not found, the value falls back to the
global setting.  If the host is in more than one aggregate and more than one
value is found, the minimum value will be used.  For information about how to
use this filter, see :ref:`host-aggregates`. See also :ref:`IoOpsFilter`.

AggregateMultiTenancyIsolation
------------------------------

Ensures hosts in tenant-isolated :ref:`host-aggregates` will only be available
to a specified set of tenants. If a host is in an aggregate that has the
``filter_tenant_id`` metadata key, the host can build instances from only that
tenant or comma-separated list of tenants. A host can be in different
aggregates. If a host does not belong to an aggregate with the metadata key,
the host can build instances from all tenants. This does not restrict the
tenant from creating servers on hosts outside the tenant-isolated aggregate.

For example, consider there are two available hosts for scheduling, HostA and
HostB. HostB is in an aggregate isolated to tenant X. A server create request
from tenant X will result in either HostA *or* HostB as candidates during
scheduling. A server create request from another tenant Y will result in only
HostA being a scheduling candidate since HostA is not part of the
tenant-isolated aggregate.

.. note:: There is a
    `known limitation <https://bugs.launchpad.net/nova/+bug/1802111>`_ with
    the number of tenants that can be isolated per aggregate using this
    filter. This limitation does not exist, however, for the
    `Tenant Isolation with Placement`_ filtering capability added in the
    18.0.0 Rocky release.

AggregateNumInstancesFilter
---------------------------

Filters host by number of instances with a per-aggregate
``max_instances_per_host`` value. If the per-aggregate value is not found, the
value falls back to the global setting.  If the host is in more than one
aggregate and thus more than one value is found, the minimum value will be
used.  For information about how to use this filter, see
:ref:`host-aggregates`.  See also :ref:`NumInstancesFilter`.

AggregateRamFilter
------------------

Filters host by RAM allocation of instances with a per-aggregate
``ram_allocation_ratio`` value. If the per-aggregate value is not found, the
value falls back to the global setting.  If the host is in more than one
aggregate and thus more than one value is found, the minimum value will be
used.  For information about how to use this filter, see
:ref:`host-aggregates`.  See also :ref:`ramfilter`.

Note the ``ram_allocation_ratio`` :ref:`bug 1804125 <bug-1804125>` restriction.

AggregateTypeAffinityFilter
---------------------------

This filter passes hosts if no ``instance_type`` key is set or the
``instance_type`` aggregate metadata value contains the name of the
``instance_type`` requested.  The value of the ``instance_type`` metadata entry
is a string that may contain either a single ``instance_type`` name or a
comma-separated list of ``instance_type`` names, such as ``m1.nano`` or
``m1.nano,m1.small``.  For information about how to use this filter, see
:ref:`host-aggregates`.

AllHostsFilter
--------------

This is a no-op filter. It does not eliminate any of the available hosts.

.. _AvailabilityZoneFilter:

AvailabilityZoneFilter
----------------------

Filters hosts by availability zone. You must enable this filter for the
scheduler to respect availability zones in requests.

.. _ComputeCapabilitiesFilter:

ComputeCapabilitiesFilter
-------------------------

Matches properties defined in extra specs for an instance type against compute
capabilities. If an extra specs key contains a colon (``:``), anything before
the colon is treated as a namespace and anything after the colon is treated as
the key to be matched.  If a namespace is present and is not ``capabilities``,
the filter ignores the namespace. For backward compatibility, also treats the
extra specs key as the key to be matched if no namespace is present; this
action is highly discouraged because it conflicts with
:ref:`AggregateInstanceExtraSpecsFilter` filter when you enable both filters.

Some virt drivers support reporting CPU traits to the Placement service. With that
feature available, you should consider using traits in flavors instead of
ComputeCapabilitiesFilter, because traits provide consistent naming for CPU
features in some virt drivers and querying traits is efficient. For more detail, please see
`Support Matrix <https://docs.openstack.org/nova/latest/user/support-matrix.html>`_,
:ref:`Required traits <extra-specs-required-traits>`,
:ref:`Forbidden traits <extra-specs-forbidden-traits>` and
`Report CPU features to the Placement service <https://specs.openstack.org/openstack/nova-specs/specs/rocky/approved/report-cpu-features-as-traits.html>`_.

Also refer to `Compute capabilities as traits`_.

.. _ComputeFilter:

ComputeFilter
-------------

Passes all hosts that are operational and enabled.

In general, you should always enable this filter.

.. _CoreFilter:

CoreFilter
----------

.. deprecated:: 19.0.0

   ``CoreFilter`` is deprecated since the 19.0.0 Stein release. VCPU
   filtering is performed natively using the Placement service when using the
   ``filter_scheduler`` driver. Furthermore, enabling CoreFilter may
   incorrectly filter out `baremetal nodes`_ which must be scheduled using
   custom resource classes.

Only schedules instances on hosts if sufficient CPU cores are available.  If
this filter is not set, the scheduler might over-provision a host based on
cores. For example, the virtual cores running on an instance may exceed the
physical cores.

You can configure this filter to enable a fixed amount of vCPU overcommitment
by using the ``cpu_allocation_ratio`` configuration option in ``nova.conf``.
The default setting is:

.. code-block:: ini

   cpu_allocation_ratio = 16.0

With this setting, if 8 vCPUs are on a node, the scheduler allows instances up
to 128 vCPU to be run on that node.

To disallow vCPU overcommitment set:

.. code-block:: ini

   cpu_allocation_ratio = 1.0

.. note::

   The Compute API always returns the actual number of CPU cores available on a
   compute node regardless of the value of the ``cpu_allocation_ratio``
   configuration key. As a result changes to the ``cpu_allocation_ratio`` are
   not reflected via the command line clients or the dashboard.  Changes to
   this configuration key are only taken into account internally in the
   scheduler.

DifferentHostFilter
-------------------

Schedules the instance on a different host from a set of instances.  To take
advantage of this filter, the requester must pass a scheduler hint, using
``different_host`` as the key and a list of instance UUIDs as the value. This
filter is the opposite of the ``SameHostFilter``.  Using the
:command:`openstack server create` command, use the ``--hint`` flag. For
example:

.. code-block:: console

   $ openstack server create --image cedef40a-ed67-4d10-800e-17455edce175 \
     --flavor 1 --hint different_host=a0cf03a5-d921-4877-bb5c-86d26cf818e1 \
     --hint different_host=8c19174f-4220-44f0-824a-cd1eeef10287 server-1

With the API, use the ``os:scheduler_hints`` key. For example:

.. code-block:: json

   {
       "server": {
           "name": "server-1",
           "imageRef": "cedef40a-ed67-4d10-800e-17455edce175",
           "flavorRef": "1"
       },
       "os:scheduler_hints": {
           "different_host": [
               "a0cf03a5-d921-4877-bb5c-86d26cf818e1",
               "8c19174f-4220-44f0-824a-cd1eeef10287"
           ]
       }
   }

.. _DiskFilter:

DiskFilter
----------

.. deprecated:: 19.0.0

   ``DiskFilter`` is deprecated since the 19.0.0 Stein release. DISK_GB
   filtering is performed natively using the Placement service when using the
   ``filter_scheduler`` driver. Furthermore, enabling DiskFilter may
   incorrectly filter out `baremetal nodes`_ which must be scheduled using
   custom resource classes.

Only schedules instances on hosts if there is sufficient disk space available
for root and ephemeral storage.

You can configure this filter to enable a fixed amount of disk overcommitment
by using the ``disk_allocation_ratio`` configuration option in the
``nova.conf`` configuration file.  The default setting disables the possibility
of the overcommitment and allows launching a VM only if there is a sufficient
amount of disk space available on a host:

.. code-block:: ini

   disk_allocation_ratio = 1.0

DiskFilter always considers the value of the ``disk_available_least`` property
and not the one of the ``free_disk_gb`` property of a hypervisor's statistics:

.. code-block:: console

   $ openstack hypervisor stats show
   +----------------------+-------+
   | Field                | Value |
   +----------------------+-------+
   | count                | 1     |
   | current_workload     | 0     |
   | disk_available_least | 14    |
   | free_disk_gb         | 27    |
   | free_ram_mb          | 15374 |
   | local_gb             | 27    |
   | local_gb_used        | 0     |
   | memory_mb            | 15886 |
   | memory_mb_used       | 512   |
   | running_vms          | 0     |
   | vcpus                | 8     |
   | vcpus_used           | 0     |
   +----------------------+-------+

As it can be viewed from the command output above, the amount of the available
disk space can be less than the amount of the free disk space.  It happens
because the ``disk_available_least`` property accounts for the virtual size
rather than the actual size of images.  If you use an image format that is
sparse or copy on write so that each virtual instance does not require a 1:1
allocation of a virtual disk to a physical storage, it may be useful to allow
the overcommitment of disk space.

When disk space is overcommitted, the value of ``disk_available_least`` can
be negative. Rather than rounding up to 0, the original negative value is
reported, as this way a user can see the amount by which they are
overcommitting, and the disk weigher can select a host which is less
overcommitted than another host.

To enable scheduling instances while overcommitting disk resources on the node,
adjust the value of the ``disk_allocation_ratio`` configuration option to
greater than ``1.0``:

.. code-block:: none

   disk_allocation_ratio > 1.0

.. note::

   If the value is set to ``>1``, we recommend keeping track of the free disk
   space, as the value approaching ``0`` may result in the incorrect
   functioning of instances using it at the moment.

.. _ImagePropertiesFilter:

ImagePropertiesFilter
---------------------

Filters hosts based on properties defined on the instance's image.  It passes
hosts that can support the specified image properties contained in the
instance. Properties include the architecture, hypervisor type, hypervisor
version (for Xen hypervisor type only), and virtual machine mode.

For example, an instance might require a host that runs an ARM-based processor,
and QEMU as the hypervisor.  You can decorate an image with these properties by
using:

.. code-block:: console

   $ openstack image set --architecture arm --property hypervisor_type=qemu \
     img-uuid

The image properties that the filter checks for are:

``architecture``
  describes the machine architecture required by the image.  Examples are
  ``i686``, ``x86_64``, ``arm``, and ``ppc64``.

``hypervisor_type``
  describes the hypervisor required by the image.  Examples are ``xen``,
  ``qemu``, and ``xenapi``.

  .. note::

     ``qemu`` is used for both QEMU and KVM hypervisor types.

``hypervisor_version_requires``
  describes the hypervisor version required by the image.  The property is
  supported for Xen hypervisor type only.  It can be used to enable support for
  multiple hypervisor versions, and to prevent instances with newer Xen tools
  from being provisioned on an older version of a hypervisor. If available, the
  property value is compared to the hypervisor version of the compute host.

  To filter the hosts by the hypervisor version, add the
  ``hypervisor_version_requires`` property on the image as metadata and pass an
  operator and a required hypervisor version as its value:

  .. code-block:: console

     $ openstack image set --property hypervisor_type=xen --property \
       hypervisor_version_requires=">=4.3" img-uuid

``vm_mode``
  describes the hypervisor application binary interface (ABI) required by the
  image. Examples are ``xen`` for Xen 3.0 paravirtual ABI, ``hvm`` for native
  ABI, ``uml`` for User Mode Linux paravirtual ABI, ``exe`` for container virt
  executable ABI.

IsolatedHostsFilter
-------------------

Allows the admin to define a special (isolated) set of images and a special
(isolated) set of hosts, such that the isolated images can only run on the
isolated hosts, and the isolated hosts can only run isolated images.  The flag
``restrict_isolated_hosts_to_isolated_images`` can be used to force isolated
hosts to only run isolated images.

The logic within the filter depends on the
``restrict_isolated_hosts_to_isolated_images`` config option, which defaults
to True. When True, a volume-backed instance will not be put on an isolated
host. When False, a volume-backed instance can go on any host, isolated or
not.

The admin must specify the isolated set of images and hosts in the
``nova.conf`` file using the ``isolated_hosts`` and ``isolated_images``
configuration options. For example:

.. code-block:: ini

   [filter_scheduler]
   isolated_hosts = server1, server2
   isolated_images = 342b492c-128f-4a42-8d3a-c5088cf27d13, ebd267a6-ca86-4d6c-9a0e-bd132d6b7d09

.. _IoOpsFilter:

IoOpsFilter
-----------

The IoOpsFilter filters hosts by concurrent I/O operations on it.  Hosts with
too many concurrent I/O operations will be filtered out.  The
``max_io_ops_per_host`` option specifies the maximum number of I/O intensive
instances allowed to run on a host.  A host will be ignored by the scheduler if
more than ``max_io_ops_per_host`` instances in build, resize, snapshot,
migrate, rescue or unshelve task states are running on it.

JsonFilter
----------

.. warning:: This filter is not enabled by default and not comprehensively
    tested, and thus could fail to work as expected in non-obvious ways.
    Furthermore, the filter variables are based on attributes of the
    `HostState`_ class which could change from release to release so usage
    of this filter is generally not recommended. Consider using other filters
    such as the :ref:`ImagePropertiesFilter` or
    :ref:`traits-based scheduling <extra-specs-required-traits>`.

The JsonFilter allows a user to construct a custom filter by passing a
scheduler hint in JSON format. The following operators are supported:

* =
* <
* >
* in
* <=
* >=
* not
* or
* and

The filter supports any attribute in the `HostState`_ class such as the
following variables:

* ``$free_ram_mb``
* ``$free_disk_mb``
* ``$hypervisor_hostname``
* ``$total_usable_ram_mb``
* ``$vcpus_total``
* ``$vcpus_used``

Using the :command:`openstack server create` command, use the ``--hint`` flag:

.. code-block:: console

   $ openstack server create --image 827d564a-e636-4fc4-a376-d36f7ebe1747 \
     --flavor 1 --hint query='[">=","$free_ram_mb",1024]' server1

With the API, use the ``os:scheduler_hints`` key:

.. code-block:: json

   {
       "server": {
           "name": "server-1",
           "imageRef": "cedef40a-ed67-4d10-800e-17455edce175",
           "flavorRef": "1"
       },
       "os:scheduler_hints": {
           "query": "[\">=\",\"$free_ram_mb\",1024]"
       }
   }

.. _HostState: https://opendev.org/openstack/nova/src/branch/master/nova/scheduler/host_manager.py

MetricsFilter
-------------

Filters hosts based on meters ``weight_setting``.  Only hosts with the
available meters are passed so that the metrics weigher will not fail due to
these hosts.

NUMATopologyFilter
------------------

Filters hosts based on the NUMA topology that was specified for the instance
through the use of flavor ``extra_specs`` in combination with the image
properties, as described in detail in the `related nova-spec document
<http://specs.openstack.org/openstack/
nova-specs/specs/juno/implemented/virt-driver-numa-placement.html>`_.  Filter
will try to match the exact NUMA cells of the instance to those of the host. It
will consider the standard over-subscription limits for each host NUMA cell,
and provide limits to the compute host accordingly.

.. note::

   If instance has no topology defined, it will be considered for any host.  If
   instance has a topology defined, it will be considered only for NUMA capable
   hosts.

.. _NumInstancesFilter:

NumInstancesFilter
------------------

Hosts that have more instances running than specified by the
``max_instances_per_host`` option are filtered out when this filter is in
place.

PciPassthroughFilter
--------------------

The filter schedules instances on a host if the host has devices that meet the
device requests in the ``extra_specs`` attribute for the flavor.

.. _RamFilter:

RamFilter
---------

.. deprecated:: 19.0.0

   ``RamFilter`` is deprecated since the 19.0.0 Stein release. MEMORY_MB
   filtering is performed natively using the Placement service when using the
   ``filter_scheduler`` driver. Furthermore, enabling RamFilter may
   incorrectly filter out `baremetal nodes`_ which must be scheduled using
   custom resource classes.

.. _baremetal nodes: https://docs.openstack.org/ironic/latest/install/configure-nova-flavors.html

Only schedules instances on hosts that have sufficient RAM available.  If this
filter is not set, the scheduler may over provision a host based on RAM (for
example, the RAM allocated by virtual machine instances may exceed the physical
RAM).

You can configure this filter to enable a fixed amount of RAM overcommitment by
using the ``ram_allocation_ratio`` configuration option in ``nova.conf``. The
default setting is:

.. code-block:: ini

   ram_allocation_ratio = 1.5

This setting enables 1.5 GB instances to run on any compute node with 1 GB of
free RAM.

RetryFilter
-----------

.. deprecated:: 20.0.0

   Since the 17.0.0 (Queens) release, the scheduler has provided alternate
   hosts for rescheduling so the scheduler does not need to be called during
   a reschedule which makes the ``RetryFilter`` useless. See the
   `Return Alternate Hosts`_ spec for details.

Filters out hosts that have already been attempted for scheduling purposes.  If
the scheduler selects a host to respond to a service request, and the host
fails to respond to the request, this filter prevents the scheduler from
retrying that host for the service request.

This filter is only useful if the :oslo.config:option:`scheduler.max_attempts`
configuration option is set to a value greater than one.

.. _Return Alternate Hosts: https://specs.openstack.org/openstack/nova-specs/specs/queens/implemented/return-alternate-hosts.html

SameHostFilter
--------------

Schedules the instance on the same host as another instance in a set of
instances. To take advantage of this filter, the requester must pass a
scheduler hint, using ``same_host`` as the key and a list of instance UUIDs as
the value.  This filter is the opposite of the ``DifferentHostFilter``.  Using
the :command:`openstack server create` command, use the ``--hint`` flag:

.. code-block:: console

   $ openstack server create --image cedef40a-ed67-4d10-800e-17455edce175 \
     --flavor 1 --hint same_host=a0cf03a5-d921-4877-bb5c-86d26cf818e1 \
     --hint same_host=8c19174f-4220-44f0-824a-cd1eeef10287 server-1

With the API, use the ``os:scheduler_hints`` key:

.. code-block:: json

   {
       "server": {
           "name": "server-1",
           "imageRef": "cedef40a-ed67-4d10-800e-17455edce175",
           "flavorRef": "1"
       },
       "os:scheduler_hints": {
           "same_host": [
               "a0cf03a5-d921-4877-bb5c-86d26cf818e1",
               "8c19174f-4220-44f0-824a-cd1eeef10287"
           ]
       }
   }

.. _ServerGroupAffinityFilter:

ServerGroupAffinityFilter
-------------------------

The ServerGroupAffinityFilter ensures that an instance is scheduled on to a
host from a set of group hosts. To take advantage of this filter, the requester
must create a server group with an ``affinity`` policy, and pass a scheduler
hint, using ``group`` as the key and the server group UUID as the value.  Using
the :command:`openstack server create` command, use the ``--hint`` flag. For
example:

.. code-block:: console

   $ openstack server group create --policy affinity group-1
   $ openstack server create --image IMAGE_ID --flavor 1 \
     --hint group=SERVER_GROUP_UUID server-1

.. _ServerGroupAntiAffinityFilter:

ServerGroupAntiAffinityFilter
-----------------------------

The ServerGroupAntiAffinityFilter ensures that each instance in a group is on a
different host. To take advantage of this filter, the requester must create a
server group with an ``anti-affinity`` policy, and pass a scheduler hint, using
``group`` as the key and the server group UUID as the value.  Using the
:command:`openstack server create` command, use the ``--hint`` flag. For
example:

.. code-block:: console

   $ openstack server group create --policy anti-affinity group-1
   $ openstack server create --image IMAGE_ID --flavor 1 \
     --hint group=SERVER_GROUP_UUID server-1

SimpleCIDRAffinityFilter
------------------------

Schedules the instance based on host IP subnet range.  To take advantage of
this filter, the requester must specify a range of valid IP address in CIDR
format, by passing two scheduler hints:

``build_near_host_ip``
  The first IP address in the subnet (for example, ``192.168.1.1``)

``cidr``
  The CIDR that corresponds to the subnet (for example, ``/24``)

Using the :command:`openstack server create` command, use the ``--hint`` flag.
For example, to specify the IP subnet ``192.168.1.1/24``:

.. code-block:: console

   $ openstack server create --image cedef40a-ed67-4d10-800e-17455edce175 \
     --flavor 1 --hint build_near_host_ip=192.168.1.1 --hint cidr=/24 server-1

With the API, use the ``os:scheduler_hints`` key:

.. code-block:: json

   {
       "server": {
           "name": "server-1",
           "imageRef": "cedef40a-ed67-4d10-800e-17455edce175",
           "flavorRef": "1"
       },
       "os:scheduler_hints": {
           "build_near_host_ip": "192.168.1.1",
           "cidr": "24"
       }
   }

.. _weights:

Weights
~~~~~~~

When resourcing instances, the filter scheduler filters and weights each host
in the list of acceptable hosts. Each time the scheduler selects a host, it
virtually consumes resources on it, and subsequent selections are adjusted
accordingly. This process is useful when the customer asks for the same large
amount of instances, because weight is computed for each requested instance.

All weights are normalized before being summed up; the host with the largest
weight is given the highest priority.

**Weighting hosts**

.. figure:: /figures/nova-weighting-hosts.png

Hosts are weighted based on the following options in the
``/etc/nova/nova.conf`` file:

.. list-table:: Host weighting options
   :header-rows: 1
   :widths: 10, 25, 60

   * - Section
     - Option
     - Description
   * - [DEFAULT]
     - ``ram_weight_multiplier``
     - By default, the scheduler spreads instances across all hosts evenly.
       Set the ``ram_weight_multiplier`` option to a negative number if you
       prefer stacking instead of spreading. Use a floating-point value.
       If the per aggregate ``ram_weight_multiplier``
       metadata is set, this multiplier will override the configuration option
       value.
   * - [DEFAULT]
     - ``disk_weight_multiplier``
     - By default, the scheduler spreads instances across all hosts evenly.
       Set the ``disk_weight_multiplier`` option to a negative number if you
       prefer stacking instead of spreading. Use a floating-point value.
       If the per aggregate ``disk_weight_multiplier``
       metadata is set, this multiplier will override the configuration option
       value.
   * - [DEFAULT]
     - ``cpu_weight_multiplier``
     - By default, the scheduler spreads instances across all hosts evenly.
       Set the ``cpu_weight_multiplier`` option to a negative number if you
       prefer stacking instead of spreading. Use a floating-point value.
       If the per aggregate ``cpu_weight_multiplier`` metadata is set, this
       multiplier will override the configuration option value.
   * - [DEFAULT]
     - ``scheduler_host_subset_size``
     - New instances are scheduled on a host that is chosen randomly from a
       subset of the N best hosts. This property defines the subset size from
       which a host is chosen. A value of 1 chooses the first host returned by
       the weighting functions. This value must be at least 1.  A value less
       than 1 is ignored, and 1 is used instead.  Use an integer value.
   * - [DEFAULT]
     - ``scheduler_weight_classes``
     - Defaults to ``nova.scheduler.weights.all_weighers``.  Hosts are then
       weighted and sorted with the largest weight winning.
   * - [DEFAULT]
     - ``io_ops_weight_multiplier``
     - Multiplier used for weighing host I/O operations. A negative value means
       a preference to choose light workload compute hosts.
       If the per aggregate ``io_ops_weight_multiplier``
       metadata is set, this multiplier will override the configuration option
       value.
   * - [filter_scheduler]
     - ``soft_affinity_weight_multiplier``
     - Multiplier used for weighing hosts for group soft-affinity.  Only a
       positive value is allowed.
   * - [filter_scheduler]
       If the per aggregate ``soft_affinity_weight_multiplier``
       metadata is set, this multiplier will override the configuration option
       value.
     - ``soft_anti_affinity_weight_multiplier``
     - Multiplier used for weighing hosts for group soft-anti-affinity.  Only a
       positive value is allowed.
       If the per aggregate ``soft_anti_affinity_weight_multiplier``
       metadata is set, this multiplier will override the configuration option
       value.
   * - [filter_scheduler]
     - ``build_failure_weight_multiplier``
     - Multiplier used for weighing hosts which have recent build failures. A
       positive value increases the significance of build failures reported by
       the host recently, making them less likely to be chosen.
       If the per aggregate ``build_failure_weight_multiplier``
       metadata is set, this multiplier will override the configuration option
       value.
   * - [metrics]
     - ``weight_multiplier``
     - Multiplier for weighting meters. Use a floating-point value.
       If the per aggregate ``metrics_weight_multiplier``
       metadata is set, this multiplier will override the configuration option
       value.
   * - [metrics]
     - ``weight_setting``
     - Determines how meters are weighted. Use a comma-separated list of
       metricName=ratio. For example: ``name1=1.0, name2=-1.0`` results in:
       ``name1.value * 1.0 + name2.value * -1.0``
   * - [metrics]
     - ``required``
     - Specifies how to treat unavailable meters:

       * True - Raises an exception. To avoid the raised exception, you should
         use the scheduler filter ``MetricFilter`` to filter out hosts with
         unavailable meters.
       * False - Treated as a negative factor in the weighting process (uses
         the ``weight_of_unavailable`` option).
   * - [metrics]
     - ``weight_of_unavailable``
     - If ``required`` is set to False, and any one of the meters set by
       ``weight_setting`` is unavailable, the ``weight_of_unavailable`` value
       is returned to the scheduler.

For example:

.. code-block:: ini

   [DEFAULT]
   scheduler_host_subset_size = 1
   scheduler_weight_classes = nova.scheduler.weights.all_weighers
   ram_weight_multiplier = 1.0
   io_ops_weight_multiplier = 2.0
   soft_affinity_weight_multiplier = 1.0
   soft_anti_affinity_weight_multiplier = 1.0
   [metrics]
   weight_multiplier = 1.0
   weight_setting = name1=1.0, name2=-1.0
   required = false
   weight_of_unavailable = -10000.0

Utilization aware scheduling
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is possible to schedule VMs using advanced scheduling decisions.  These
decisions are made based on enhanced usage statistics encompassing data like
memory cache utilization, memory bandwidth utilization, or network bandwidth
utilization. This is disabled by default.  The administrator can configure how
the metrics are weighted in the configuration file by using the
``weight_setting`` configuration option in the ``nova.conf`` configuration
file.  For example to configure metric1 with ratio1 and metric2 with ratio2:

.. code-block:: ini

   weight_setting = "metric1=ratio1, metric2=ratio2"

.. _host-aggregates:

Host aggregates and availability zones
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Host aggregates are a mechanism for partitioning hosts in an OpenStack cloud,
or a region of an OpenStack cloud, based on arbitrary characteristics.
Examples where an administrator may want to do this include where a group of
hosts have additional hardware or performance characteristics.

Host aggregates are not explicitly exposed to users.  Instead administrators
map flavors to host aggregates.  Administrators do this by setting metadata on
a host aggregate, and matching flavor extra specifications.  The scheduler then
endeavors to match user requests for instance of the given flavor to a host
aggregate with the same key-value pair in its metadata.  Compute nodes can be
in more than one host aggregate. Weight multipliers can be controlled on a
per-aggregate basis by setting the desired ``xxx_weight_multiplier`` aggregate
metadata.
Administrators are able to optionally expose a host aggregate as an
availability zone. Availability zones are different from host aggregates in
that they are explicitly exposed to the user, and hosts can only be in a single
availability zone. Administrators can configure a default availability zone
where instances will be scheduled when the user fails to specify one.

Command-line interface
----------------------

The :command:`nova` command-line client supports the following
aggregate-related commands.

nova aggregate-list
  Print a list of all aggregates.

nova aggregate-create <name> [<availability-zone>]
  Create a new aggregate named ``<name>``, and optionally in availability zone
  ``[<availability-zone>]`` if specified. The command returns the ID of the
  newly created aggregate. Hosts can be made available to multiple host
  aggregates. Be careful when adding a host to an additional host aggregate
  when the host is also in an availability zone. Pay attention when using the
  :command:`nova aggregate-set-metadata` and :command:`nova aggregate-update`
  commands to avoid user confusion when they boot instances in different
  availability zones.  An error occurs if you cannot add a particular host to
  an aggregate zone for which it is not intended.

nova aggregate-delete <aggregate>
  Delete an aggregate with its ``<id>`` or ``<name>``.

nova aggregate-show <aggregate>
  Show details of the aggregate with its ``<id>`` or ``<name>``.

nova aggregate-add-host <aggregate> <host>
  Add host with name ``<host>`` to aggregate with its ``<id>`` or ``<name>``.

nova aggregate-remove-host <aggregate> <host>
  Remove the host with name ``<host>`` from the aggregate with its ``<id>``
  or ``<name>``.

nova aggregate-set-metadata <aggregate> <key=value> [<key=value> ...]
  Add or update metadata (key-value pairs) associated with the aggregate with
  its ``<id>`` or ``<name>``.

nova aggregate-update [--name <name>] [--availability-zone <availability-zone>] <aggregate>
  Update the name and/or availability zone for the aggregate.

nova host-list
  List all hosts by service. It has been deprecated since microversion 2.43.
  Use :command:`nova hypervisor-list` instead.

nova hypervisor-list [--matching <hostname>] [--marker <marker>] [--limit <limit>]
  List hypervisors.

nova host-update [--status <enable|disable>] [--maintenance <enable|disable>] <hostname>
  Put/resume host into/from maintenance. It has been deprecated since
  microversion 2.43. To enable or disable a service,
  use :command:`nova service-enable` or :command:`nova service-disable` instead.

nova service-enable <id>
  Enable the service.

nova service-disable [--reason <reason>] <id>
  Disable the service.

.. note::

   Only administrators can access these commands. If you try to use these
   commands and the user name and tenant that you use to access the Compute
   service do not have the ``admin`` role or the appropriate privileges, these
   errors occur:

   .. code-block:: console

      ERROR: Policy doesn't allow compute_extension:aggregates to be performed. (HTTP 403) (Request-ID: req-299fbff6-6729-4cef-93b2-e7e1f96b4864)

   .. code-block:: console

      ERROR: Policy doesn't allow compute_extension:hosts to be performed. (HTTP 403) (Request-ID: req-ef2400f6-6776-4ea3-b6f1-7704085c27d1)

.. _config-sch-for-aggs:

Configure scheduler to support host aggregates
----------------------------------------------

One common use case for host aggregates is when you want to support scheduling
instances to a subset of compute hosts because they have a specific capability.
For example, you may want to allow users to request compute hosts that have SSD
drives if they need access to faster disk I/O, or access to compute hosts that
have GPU cards to take advantage of GPU-accelerated code.

To configure the scheduler to support host aggregates, the
:oslo.config:option:`filter_scheduler.enabled_filters` configuration option must
contain the ``AggregateInstanceExtraSpecsFilter`` in addition to the other filters
used by the scheduler. Add the following line to ``/etc/nova/nova.conf`` on the
host that runs the ``nova-scheduler`` service to enable host aggregates filtering,
as well as the other filters that are typically enabled:

.. code-block:: ini

   [filter_scheduler]
   enabled_filters=...,AggregateInstanceExtraSpecsFilter

Example: Specify compute hosts with SSDs
----------------------------------------

This example configures the Compute service to enable users to request nodes
that have solid-state drives (SSDs). You create a ``fast-io`` host aggregate in
the ``nova`` availability zone and you add the ``ssd=true`` key-value pair to
the aggregate. Then, you add the ``node1``, and ``node2`` compute nodes to it.

.. code-block:: console

   $ openstack aggregate create --zone nova fast-io
   +-------------------+----------------------------+
   | Field             | Value                      |
   +-------------------+----------------------------+
   | availability_zone | nova                       |
   | created_at        | 2016-12-22T07:31:13.013466 |
   | deleted           | False                      |
   | deleted_at        | None                       |
   | id                | 1                          |
   | name              | fast-io                    |
   | updated_at        | None                       |
   +-------------------+----------------------------+

   $ openstack aggregate set --property ssd=true 1
   +-------------------+----------------------------+
   | Field             | Value                      |
   +-------------------+----------------------------+
   | availability_zone | nova                       |
   | created_at        | 2016-12-22T07:31:13.000000 |
   | deleted           | False                      |
   | deleted_at        | None                       |
   | hosts             | []                         |
   | id                | 1                          |
   | name              | fast-io                    |
   | properties        | ssd='true'                 |
   | updated_at        | None                       |
   +-------------------+----------------------------+

   $ openstack aggregate add host 1 node1
   +-------------------+--------------------------------------------------+
   | Field             | Value                                            |
   +-------------------+--------------------------------------------------+
   | availability_zone | nova                                             |
   | created_at        | 2016-12-22T07:31:13.000000                       |
   | deleted           | False                                            |
   | deleted_at        | None                                             |
   | hosts             | [u'node1']                                       |
   | id                | 1                                                |
   | metadata          | {u'ssd': u'true', u'availability_zone': u'nova'} |
   | name              | fast-io                                          |
   | updated_at        | None                                             |
   +-------------------+--------------------------------------------------+

   $ openstack aggregate add host 1 node2
   +-------------------+--------------------------------------------------+
   | Field             | Value                                            |
   +-------------------+--------------------------------------------------+
   | availability_zone | nova                                             |
   | created_at        | 2016-12-22T07:31:13.000000                       |
   | deleted           | False                                            |
   | deleted_at        | None                                             |
   | hosts             | [u'node1', u'node2']                             |
   | id                | 1                                                |
   | metadata          | {u'ssd': u'true', u'availability_zone': u'nova'} |
   | name              | fast-io                                          |
   | updated_at        | None                                             |
   +-------------------+--------------------------------------------------+

Use the :command:`openstack flavor create` command to create the ``ssd.large``
flavor called with an ID of 6, 8 GB of RAM, 80 GB root disk, and 4 vCPUs.

.. code-block:: console

   $ openstack flavor create --id 6 --ram 8192 --disk 80 --vcpus 4 ssd.large
   +----------------------------+-----------+
   | Field                      | Value     |
   +----------------------------+-----------+
   | OS-FLV-DISABLED:disabled   | False     |
   | OS-FLV-EXT-DATA:ephemeral  | 0         |
   | disk                       | 80        |
   | id                         | 6         |
   | name                       | ssd.large |
   | os-flavor-access:is_public | True      |
   | ram                        | 8192      |
   | rxtx_factor                | 1.0       |
   | swap                       |           |
   | vcpus                      | 4         |
   +----------------------------+-----------+

Once the flavor is created, specify one or more key-value pairs that match the
key-value pairs on the host aggregates with scope
``aggregate_instance_extra_specs``. In this case, that is the
``aggregate_instance_extra_specs:ssd=true`` key-value pair.  Setting a
key-value pair on a flavor is done using the :command:`openstack flavor set`
command.

.. code-block:: console

   $ openstack flavor set --property aggregate_instance_extra_specs:ssd=true ssd.large

Once it is set, you should see the ``extra_specs`` property of the
``ssd.large`` flavor populated with a key of ``ssd`` and a corresponding value
of ``true``.

.. code-block:: console

   $ openstack flavor show ssd.large
   +----------------------------+-------------------------------------------+
   | Field                      | Value                                     |
   +----------------------------+-------------------------------------------+
   | OS-FLV-DISABLED:disabled   | False                                     |
   | OS-FLV-EXT-DATA:ephemeral  | 0                                         |
   | disk                       | 80                                        |
   | id                         | 6                                         |
   | name                       | ssd.large                                 |
   | os-flavor-access:is_public | True                                      |
   | properties                 | aggregate_instance_extra_specs:ssd='true' |
   | ram                        | 8192                                      |
   | rxtx_factor                | 1.0                                       |
   | swap                       |                                           |
   | vcpus                      | 4                                         |
   +----------------------------+-------------------------------------------+

Now, when a user requests an instance with the ``ssd.large`` flavor,
the scheduler only considers hosts with the ``ssd=true`` key-value pair.
In this example, these are ``node1`` and ``node2``.

Aggregates in Placement
-----------------------

Aggregates also exist in placement and are not the same thing as host
aggregates in nova. These aggregates are defined (purely) as groupings
of related resource providers. Since compute nodes in nova are
represented in placement as resource providers, they can be added to a
placement aggregate as well. For example, get the uuid of the compute
node using :command:`openstack hypervisor list` and add it to an
aggregate in placement using :command:`openstack resource provider aggregate
set`.

.. code-block:: console

  $ openstack --os-compute-api-version=2.53 hypervisor list
  +--------------------------------------+---------------------+-----------------+-----------------+-------+
  | ID                                   | Hypervisor Hostname | Hypervisor Type | Host IP         | State |
  +--------------------------------------+---------------------+-----------------+-----------------+-------+
  | 815a5634-86fb-4e1e-8824-8a631fee3e06 | node1               | QEMU            | 192.168.1.123   | up    |
  +--------------------------------------+---------------------+-----------------+-----------------+-------+

  $ openstack --os-placement-api-version=1.2 resource provider aggregate set --aggregate df4c74f3-d2c4-4991-b461-f1a678e1d161 815a5634-86fb-4e1e-8824-8a631fee3e06

Some scheduling filter operations can be performed by placement for
increased speed and efficiency.

.. note::

    The nova-api service attempts (as of nova 18.0.0) to automatically mirror
    the association of a compute host with an aggregate when an administrator
    adds or removes a host to/from a nova host aggregate. This should alleviate
    the need to manually create those association records in the placement API
    using the ``openstack resource provider aggregate set`` CLI invocation.

Tenant Isolation with Placement
-------------------------------

In order to use placement to isolate tenants, there must be placement
aggregates that match the membership and UUID of nova host aggregates
that you want to use for isolation. The same key pattern in aggregate
metadata used by the `AggregateMultiTenancyIsolation`_ filter controls
this function, and is enabled by setting
`[scheduler]/limit_tenants_to_placement_aggregate=True`.

.. code-block:: console

  $ openstack --os-compute-api-version=2.53 aggregate create myagg
  +-------------------+--------------------------------------+
  | Field             | Value                                |
  +-------------------+--------------------------------------+
  | availability_zone | None                                 |
  | created_at        | 2018-03-29T16:22:23.175884           |
  | deleted           | False                                |
  | deleted_at        | None                                 |
  | id                | 4                                    |
  | name              | myagg                                |
  | updated_at        | None                                 |
  | uuid              | 019e2189-31b3-49e1-aff2-b220ebd91c24 |
  +-------------------+--------------------------------------+

  $ openstack --os-compute-api-version=2.53 aggregate add host myagg node1
  +-------------------+--------------------------------------+
  | Field             | Value                                |
  +-------------------+--------------------------------------+
  | availability_zone | None                                 |
  | created_at        | 2018-03-29T16:22:23.175884           |
  | deleted           | False                                |
  | deleted_at        | None                                 |
  | hosts             | [u'node1']                           |
  | id                | 4                                    |
  | name              | myagg                                |
  | updated_at        | None                                 |
  | uuid              | 019e2189-31b3-49e1-aff2-b220ebd91c24 |
  +-------------------+--------------------------------------+

  $ openstack project list -f value | grep 'demo'
  9691591f913949818a514f95286a6b90 demo

  $ openstack aggregate set --property filter_tenant_id=9691591f913949818a514f95286a6b90 myagg

  $ openstack --os-placement-api-version=1.2 resource provider aggregate set --aggregate 019e2189-31b3-49e1-aff2-b220ebd91c24 815a5634-86fb-4e1e-8824-8a631fee3e06

Note that the ``filter_tenant_id`` metadata key can be optionally suffixed
with any string for multiple tenants, such as ``filter_tenant_id3=$tenantid``.

Availability Zones with Placement
---------------------------------

In order to use placement to honor availability zone requests, there must be
placement aggregates that match the membership and UUID of nova host aggregates
that you assign as availability zones. The same key in aggregate metadata used
by the `AvailabilityZoneFilter` filter controls this function, and is enabled by
setting `[scheduler]/query_placement_for_availability_zone=True`.

.. code-block:: console

  $ openstack --os-compute-api-version=2.53 aggregate create myaz
  +-------------------+--------------------------------------+
  | Field             | Value                                |
  +-------------------+--------------------------------------+
  | availability_zone | None                                 |
  | created_at        | 2018-03-29T16:22:23.175884           |
  | deleted           | False                                |
  | deleted_at        | None                                 |
  | id                | 4                                    |
  | name              | myaz                                 |
  | updated_at        | None                                 |
  | uuid              | 019e2189-31b3-49e1-aff2-b220ebd91c24 |
  +-------------------+--------------------------------------+

  $ openstack --os-compute-api-version=2.53 aggregate add host myaz node1
  +-------------------+--------------------------------------+
  | Field             | Value                                |
  +-------------------+--------------------------------------+
  | availability_zone | None                                 |
  | created_at        | 2018-03-29T16:22:23.175884           |
  | deleted           | False                                |
  | deleted_at        | None                                 |
  | hosts             | [u'node1']                           |
  | id                | 4                                    |
  | name              | myagg                                |
  | updated_at        | None                                 |
  | uuid              | 019e2189-31b3-49e1-aff2-b220ebd91c24 |
  +-------------------+--------------------------------------+

  $ openstack aggregate set --property availability_zone=az002 myaz

  $ openstack --os-placement-api-version=1.2 resource provider aggregate set --aggregate 019e2189-31b3-49e1-aff2-b220ebd91c24 815a5634-86fb-4e1e-8824-8a631fee3e06

With the above configuration, the `AvailabilityZoneFilter` filter can be disabled
in `[filter_scheduler]/enabled_filters` while retaining proper behavior (and doing
so with the higher performance of placement's implementation).

XenServer hypervisor pools to support live migration
----------------------------------------------------

When using the XenAPI-based hypervisor, the Compute service uses host
aggregates to manage XenServer Resource pools, which are used in supporting
live migration.

Allocation ratios
~~~~~~~~~~~~~~~~~

The following configuration options exist to control allocation ratios
per compute node to support over-commit of resources:

* :oslo.config:option:`cpu_allocation_ratio`: allows overriding the VCPU
  inventory allocation ratio for a compute node
* :oslo.config:option:`ram_allocation_ratio`: allows overriding the MEMORY_MB
  inventory allocation ratio for a compute node
* :oslo.config:option:`disk_allocation_ratio`: allows overriding the DISK_GB
  inventory allocation ratio for a compute node

Prior to the 19.0.0 Stein release, if left unset, the ``cpu_allocation_ratio``
defaults to 16.0, the ``ram_allocation_ratio`` defaults to 1.5, and the
``disk_allocation_ratio`` defaults to 1.0.

Starting with the 19.0.0 Stein release, the following configuration options
control the initial allocation ratio values for a compute node:

* :oslo.config:option:`initial_cpu_allocation_ratio`: the initial VCPU
  inventory allocation ratio for a new compute node record, defaults to 16.0
* :oslo.config:option:`initial_ram_allocation_ratio`: the initial MEMORY_MB
  inventory allocation ratio for a new compute node record, defaults to 1.5
* :oslo.config:option:`initial_disk_allocation_ratio`: the initial DISK_GB
  inventory allocation ratio for a new compute node record, defaults to 1.0

Scheduling considerations
-------------------------

The allocation ratio configuration is used both during reporting of compute
node `resource provider inventory`_ to the placement service and during
scheduling.

The (deprecated) `CoreFilter`_, `DiskFilter`_ and `RamFilter`_ filters will use
the allocation ratio from the compute node directly when calculating available
capacity on a given node during scheduling.

The `AggregateCoreFilter`_, `AggregateDiskFilter`_ and `AggregateRamFilter`_
filters allow overriding per-compute allocation ratios by setting an allocation
ratio value using host aggregate metadata. This provides a convenient way to
manage a group of compute hosts with similar allocation ratios while leaving
the configuration settings alone.

.. _bug-1804125:

.. note:: Regarding the `AggregateCoreFilter`_, `AggregateDiskFilter`_ and
   `AggregateRamFilter`_, starting in 15.0.0 (Ocata) there is a behavior
   change where aggregate-based overcommit ratios will no longer be honored
   during scheduling for the FilterScheduler. Instead, overcommit values must
   be set on a per-compute-node basis in the Nova configuration files.

   If you have been relying on per-aggregate overcommit, during your upgrade,
   you must change to using per-compute-node overcommit ratios in order for
   your scheduling behavior to stay consistent. Otherwise, you may notice
   increased NoValidHost scheduling failures as the aggregate-based overcommit
   is no longer being considered.

   See `bug 1804125 <https://bugs.launchpad.net/nova/+bug/1804125>`_ for more
   details.

.. _resource provider inventory: https://developer.openstack.org/api-ref/placement/?expanded=#resource-provider-inventories

Usage scenarios
---------------

Since allocation ratios can be set via nova configuration, host aggregate
metadata and the placement API, it can be confusing to know which should be
used. This really depends on your scenario. A few common scenarios are detailed
here.

1. When the deployer wants to **always** set an override value for a resource
   on a compute node, the deployer would ensure that the
   ``[DEFAULT]/cpu_allocation_ratio``, ``[DEFAULT]/ram_allocation_ratio`` and
   ``[DEFAULT]/disk_allocation_ratio`` configuration options are set to a
   non-None value (or greater than 0.0 before the 19.0.0 Stein release). This
   will make the ``nova-compute`` service overwrite any externally-set
   allocation ratio values set via the placement REST API.

2. When the deployer wants to set an **initial** value for a compute node
   allocation ratio but wants to allow an admin to adjust this afterwards
   without making any configuration file changes, the deployer would set the
   ``[DEFAULT]/initial_cpu_allocation_ratio``,
   ``[DEFAULT]/initial_ram_allocation_ratio`` and
   ``[DEFAULT]/initial_disk_allocation_ratio`` configuration options and then
   manage the allocation ratios using the placement REST API (or
   `osc-placement`_ command line interface). For example:

   .. code-block:: console

     $ openstack resource provider inventory set --resource VCPU:allocation_ratio=1.0 815a5634-86fb-4e1e-8824-8a631fee3e06

   Note the :ref:`bug 1804125 <bug-1804125>` restriction.

3. When the deployer wants to **always** use the placement API to set
   allocation ratios, then the deployer should ensure that
   ``[DEFAULT]/xxx_allocation_ratio`` options are all set to None (the
   default since 19.0.0 Stein, 0.0 before Stein) and then
   manage the allocation ratios using the placement REST API (or
   `osc-placement`_ command line interface).

   This scenario is the workaround for
   `bug 1804125 <https://bugs.launchpad.net/nova/+bug/1804125>`_.

.. _osc-placement: https://docs.openstack.org/osc-placement/latest/index.html

Cells considerations
~~~~~~~~~~~~~~~~~~~~

By default cells are enabled for scheduling new instances but they can be
disabled (new schedulings to the cell are blocked). This may be useful for
users while performing cell maintenance, failures or other interventions. It is
to be noted that creating pre-disabled cells and enabling/disabling existing
cells should either be followed by a restart or SIGHUP of the nova-scheduler
service for the changes to take effect.

Command-line interface
----------------------

The :command:`nova-manage` command-line client supports the cell-disable
related commands. To enable or disable a cell, use
:command:`nova-manage cell_v2 update_cell` and to create pre-disabled cells,
use :command:`nova-manage cell_v2 create_cell`. See the
:ref:`man-page-cells-v2` man page for details on command usage.


.. _compute-capabilities-as-traits:

Compute capabilities as traits
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Starting with the 19.0.0 Stein release, the ``nova-compute`` service will
report certain ``COMPUTE_*`` traits based on its compute driver capabilities
to the placement service. The traits will be associated with the resource
provider for that compute service. These traits can be used during scheduling
by configuring flavors with
:ref:`Required traits <extra-specs-required-traits>` or
:ref:`Forbidden traits <extra-specs-forbidden-traits>`. For example, if you
have a host aggregate with a set of compute nodes that support multi-attach
volumes, you can restrict a flavor to that aggregate by adding the
``trait:COMPUTE_VOLUME_MULTI_ATTACH=required`` extra spec to the flavor and
then restrict the flavor to the aggregate
:ref:`as normal <config-sch-for-aggs>`.

Here is an example of a libvirt compute node resource provider that is
exposing some CPU features as traits, driver capabilities as traits, and a
custom trait denoted by the ``CUSTOM_`` prefix:

.. code-block:: console

  $ openstack --os-placement-api-version 1.6 resource provider trait list \
  > d9b3dbc4-50e2-42dd-be98-522f6edaab3f --sort-column name
  +---------------------------------------+
  | name                                  |
  +---------------------------------------+
  | COMPUTE_DEVICE_TAGGING                |
  | COMPUTE_NET_ATTACH_INTERFACE          |
  | COMPUTE_NET_ATTACH_INTERFACE_WITH_TAG |
  | COMPUTE_TRUSTED_CERTS                 |
  | COMPUTE_VOLUME_ATTACH_WITH_TAG        |
  | COMPUTE_VOLUME_EXTEND                 |
  | COMPUTE_VOLUME_MULTI_ATTACH           |
  | CUSTOM_IMAGE_TYPE_RBD                 |
  | HW_CPU_X86_MMX                        |
  | HW_CPU_X86_SSE                        |
  | HW_CPU_X86_SSE2                       |
  | HW_CPU_X86_SVM                        |
  +---------------------------------------+

**Rules**

There are some rules associated with capability-defined traits.

1. The compute service "owns" these traits and will add/remove them when the
   ``nova-compute`` service starts and when the ``update_available_resource``
   periodic task runs, with run intervals controlled by config option
   :oslo.config:option:`update_resources_interval`.

2. The compute service will not remove any custom traits set on the resource
   provider externally, such as the ``CUSTOM_IMAGE_TYPE_RBD`` trait in the
   example above.

3. If compute-owned traits are removed from the resource provider externally,
   for example by running ``openstack resource provider trait delete <rp_uuid>``,
   the compute service will add its traits again on restart or SIGHUP.

4. If a compute trait is set on the resource provider externally which is not
   supported by the driver, for example by adding the ``COMPUTE_VOLUME_EXTEND``
   trait when the driver does not support that capability, the compute service
   will automatically remove the unsupported trait on restart or SIGHUP.

5. Compute capability traits are standard traits defined in the `os-traits`_
   library.

.. _os-traits: https://opendev.org/openstack/os-traits/src/branch/master/os_traits/compute

:ref:`Further information on capabilities and traits
<taxonomy_of_traits_and_capabilities>` can be found in the
:doc:`Technical Reference Deep Dives section </reference/index>`.
