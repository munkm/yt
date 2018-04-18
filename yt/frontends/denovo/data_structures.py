"""
Denovo data structures



"""

#-----------------------------------------------------------------------------
# Copyright (c) 2013, yt Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
#-----------------------------------------------------------------------------

import os
import numpy as np
import weakref
from yt.utilities.on_demand_imports import _h5py as h5py
from yt.utilities.logger import ytLogger as mylog
from yt.utilities.file_handler import HDF5FileHandler
from yt.funcs import setdefaultattr

from yt.data_objects.unstructured_mesh import \
    SemiStructuredMesh
from yt.geometry.unstructured_mesh_handler import \
    UnstructuredIndex
from yt.data_objects.static_output import \
    Dataset

from .fields import DenovoFieldInfo

class DenovoMesh(SemiStructuredMesh):
    _connectivity_length = 8
    _index_offset = 0

class DenovoIndex(UnstructuredIndex):

    def __init__(self, ds, dataset_type='denovo'):
        self.dataset_type = dataset_type
        self.dataset = weakref.proxy(ds)

        # for now, the index file is the dataset!
        self.index_filename = self.dataset.parameter_filename
        self.directory = os.path.dirname(self.index_filename)
        self._fhandle = h5py.File(self.index_filename, 'r')

        # float type for the simulation edges and must be float64 now
        self.float_type = np.float64
        super(DenovoIndex, self).__init__(ds, dataset_type)

    def _initialize_mesh(self):
        from yt.frontends.stream.data_structures import hexahedral_connectivity
        coords, conn =hexahedral_connectivity(
                self.dataset.parameters['mesh_x'],
                self.dataset.parameters['mesh_y'],
                self.dataset.parameters['mesh_z'])
        self.meshes = [DenovoMesh(0, self.index_filename, conn, coords, self)]


    def _detect_output_fields(self):

        if 'mesh_g' in self.dataset.parameters:
            num_groups = len(self.dataset.parameters['mesh_g'])
        else:
            num_groups = 0

        mylog.debug("There are {} energy groups".format(num_groups))


        # Here we will create the output fields. If an energy group mesh
        # exists, we'll create several energy group field types with field
        # names that are associated with the mesh data in the denovo output
        # file.
        if num_groups > 0:
            self.field_list = []
            for group in self.dataset.parameters['mesh_g']:
                self._create_group_fields(group)

        # If an energy group mesh does not exist, then the mesh data will be
        # contained in a 'denovo' field type, rather than an energy group field
        # type.
        else:
            self.field_list = [("denovo", key) for key, val in
                    self._fhandle['/denovo/db/hdf5_db'].items() if val.value]

            # right now we don't want to read in a few of these fields, so we'll
            # manually delete them here until support can be added for them
            # later.

            if ('denovo','angular_mesh') in self.field_list:
                self.field_list.remove(('denovo','angular_mesh'))
            self.field_list.remove(('denovo','block'))


    def _create_group_fields(self, group_number):
        field_type = 'egroup_%03i' %group_number
        self.field_list.extend([(field_type, key) for key, val in
                self._fhandle['/denovo/db/hdf5_db'].items() if val.value])
        if (field_type, 'angular_mesh') in self.field_list:
            self.field_list.remove((field_type, 'angular_mesh'))
        self.field_list.remove((field_type, 'block'))

    def _count_grids(self):
        self.num_grids=1


class DenovoDataset(Dataset):
    _index_class = DenovoIndex
    _field_info_class = DenovoFieldInfo
    _suffix = ".out.h5"

    def __init__(self, filename,
                 dataset_type='denovo',
                 storage_filename=None,
                 units_override=None):

        self.fluid_types += ('denovo',)
        self._handle = HDF5FileHandler(filename)
        self.dataset_type = dataset_type

        self.geometry = 'cartesian'

        super(DenovoDataset, self).__init__(filename, dataset_type,
                units_override=units_override)
        self.storage_filename = storage_filename
        self.filename=filename

        # Note for later: if this is set in _parse_parameter_file, does it need
        # to be set here?
        self.cosmological_simulation = False

    def _set_code_unit_attributes(self):

        # For now set the length mass and time units to what we expect.
        # Denovo does not currently output what units the flux is in
        # explicitly, but these units are implied.


        setdefaultattr(self, 'length_unit', self.quan(1.0, "cm"))
        setdefaultattr(self, 'mass_unit', self.quan(1.0, "g"))
        setdefaultattr(self, 'time_unit', self.quan(1.0, "s"))
        #
        pass

    def _parse_parameter_file(self):
        #
        self.unique_identifier = self.parameter_filename
        self._handle = h5py.File(self.parameter_filename, "r")
        self.parameters = self._load_parameters()
        self.domain_left_edge, self.domain_right_edge = self._load_domain_edge()
        self.domain_dimensions = np.array([2,2,2])
        self.dimensionality = len(self.domain_dimensions)
        self._load_energy_fluid_types()

        # We know that Denovo datasets are never periodic, so periodicity will
        # be set to false.
        self.periodicity = (False, False, False)

        # There is no time-dependence in the denovo solutions at this time, so
        # this will be set to 0.0
        self.current_time = 0.0

        # The next few parameters are set to 0 because Denovo is a
        # non-cosmological simulation tool.

        self.cosmological_simulation = 0
        self.current_redshift = 0
        self.omega_lambda = 0
        self.omega_matter = 0
        self.hubble_constant = 0
        pass

    def _load_parameters(self):
        """

        loads in all of the parameters located in the 'denovo' group that are
        not groups themselves and are not flux or source fields.

        """

        for key,val in self._handle["/denovo"].items():
            if isinstance(val, h5py.Dataset):
                # skip the fields that will be stored elsewhere
                if any([key == 'flux', key == 'source', key == 'angular_flux',
                    key == 'block']):
                    pass
                else:
                    self.parameters[key]=val.value

        return self.parameters

    def _load_energy_fluid_types(self):
        """

        checks to see if mesh data is binned by energy, creates fluid types
        that correspond with energy bins if they do.

        """

        if len(self.parameters['mesh_g']) > 0:
            for group_number in self.parameters['mesh_g']:
                self.fluid_types += ('egroup_%03i' %group_number,)
        else:
            return

    def _load_domain_edge(self):
        """

        Loads the boundaries for the domain edge using the min and max values
        obtained from the x, y, and z meshes.

        """

        mylog.info("calculating domain boundaries")

        if 'mesh_x' in self.parameters:
            left_edge = np.array([self.parameters['mesh_x'].min(),
            self.parameters['mesh_y'].min(),
            self.parameters['mesh_z'].min()])

            right_edge = np.array([self.parameters['mesh_x'].max(),
            self.parameters['mesh_y'].max(),
            self.parameters['mesh_z'].max()])

        else:
            left_edge = []
            right_edge = []

        return left_edge, right_edge


    @classmethod
    def _is_valid(self, *args, **kwargs):

        # warn_h5py(args[0])

        try:
            fileh = h5py.File(args[0], 'r')

            # for now check that denovo is in the solution file. This will need
            # to be updated for fwd/adjoint runs in the future with multiple
            # arguments for a valid dataset.
            valid = "denovo" in fileh["/"] or "denovo-forward" in fileh["/"]
            fileh.close()
            return valid
        except:
            pass

        return False
