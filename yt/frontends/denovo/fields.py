"""
Denovo-specific fields



"""

#-----------------------------------------------------------------------------
# Copyright (c) 2013, yt Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
#-----------------------------------------------------------------------------

from yt.fields.field_info_container import \
    FieldInfoContainer

flux_units = " 1 / code_length**2"
angular_flux_units = " 1 / code_length**2 / steradian "
density_units = "code_mass / code_length**3"
source_units = "1"


class DenovoFieldInfo(FieldInfoContainer):
    known_other_fields = (
        ("source", (source_units, ["source_strength"], None)),
        ("flux", (flux_units, ["scalar_flux"], r"\phi")),
        ("uncflux", (flux_units, ["uncollided_flux"], r"\phi_{uncollided}")),
        ("angular_flux", (angular_flux_units, [], r"\Psi")),
        ("ww_lower", ("", ["ww_lower_bound"], None)),
    )

    known_particle_fields = (
        # At this time Denovo does not output particle fields, so there are no
        # particle fields defined in this file.
    )

    def setup_fluid_fields(self):
        # Here we do anything that might need info about the dataset.
        # You can use self.alias, self.add_output_field (for on-disk fields)
        # and self.add_field (for derived fields).
        pass

    def setup_particle_fields(self, ptype):
        # Becuase there are no particle types in Denovo, this is empty for now.
        pass

