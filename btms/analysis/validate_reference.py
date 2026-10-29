"""Offline Chen2020 SPMe reference: never imported by the environment or trainer."""
import os
os.environ['PYBAMM_DISABLE_TELEMETRY'] = 'true'
import json
from pathlib import Path
import numpy as np
import pybamm
from btms.plant.battery_electrical import Electrical


def main():
    parameter = pybamm.ParameterValues('Chen2020')
    rows = []
    for soc in [.15, .3, .7, .9]:
        model = pybamm.lithium_ion.SPMe()
        simulation = pybamm.Simulation(model, parameter_values=parameter)
        solution = simulation.solve(np.linspace(0, 60, 61), initial_soc=soc)
        ocv = solution['Battery open-circuit voltage [V]'].entries
        voltage = solution['Terminal voltage [V]'].entries
        current = 5.
        equivalent = Electrical(soc=soc)
        r0 = (ocv[0]-voltage[0])/current
        r60 = (ocv[-1]-voltage[-1])/current
        rows.append(dict(soc=soc, reference_ocv_v=float(ocv[0]),
                  model_ocv_v=equivalent.ocv()/96,
                  reference_r0_cell_ohm=float(r0), reference_r60_cell_ohm=float(r60),
                  model_r0_cell_ohm=equivalent.resistance(25)*34/96,
                  model_r60_cell_ohm=(equivalent.resistance(25)+equivalent.r1*(1-np.exp(-2)))*34/96))
    layers = ['Negative current collector','Negative electrode','Separator',
              'Positive electrode','Positive current collector']
    weighted = sum(parameter[f'{x} thickness [m]']*parameter[f'{x} density [kg.m-3]']*
                   parameter[f'{x} specific heat capacity [J.kg-1.K-1]'] for x in layers)
    thickness = sum(parameter[f'{x} thickness [m]'] for x in layers)
    cell_capacity = weighted/thickness*parameter['Cell volume [m3]']
    result = dict(reference='Chen et al. 2020, DOI 10.1149/1945-7111/ab9050; PyBaMM SPMe',
          pybamm_version=pybamm.__version__, pulse='5 A discharge for 60 s at 25 C',
          pack_topology='96s34p, 5 Ah cells', rows=rows,
          reference_cell_heat_capacity_j_k=float(cell_capacity),
          reference_cell_only_pack_heat_capacity_j_k=float(cell_capacity*96*34),
          model_pack_heat_capacity_j_k=240000.,
          note='Pack includes enclosure/cold plates; conductances and hardware mass are engineering assumptions. This is a reduced-model cross-check, not experimental pack validation.')
    path = Path(__file__).resolve().parents[2]/'report/results/parameter_reference.json'
    path.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
