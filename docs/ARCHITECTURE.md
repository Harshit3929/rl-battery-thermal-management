# Architecture and workflow

## 30-second mental model

Official speed trace -> road loads -> battery current -> electrical heat -> four
thermal modules -> coolant loop. A controller chooses pump, fan and chiller
commands. Every controller shares the same plant, objective and episode manifests.
Training and scientific results come only after plant consistency checks and the
unshielded null-controller hardness gate.

## Read the code in this order

1. `plant/drive_cycles.py`: official trace provenance and unit conversions.
2. `plant/vehicle.py`: acceleration and road loads turn speed into terminal demand.
3. `plant/battery_electrical.py`: SoC, voltage drop and polarization heat.
4. `plant/battery_thermal.py`: genuine spatial temperatures and coolant warming.
5. `plant/cooling.py`: actuator regimes and auxiliary energy.
6. `plant/pack.py`: integration and conservation accounting.
7. `tests/test_plant.py`: limiting cases that the model must preserve.

## Why the coolant has a state

A fixed coolant inlet would silently act as an unlimited external refrigerator.
Instead the finite coolant inventory receives heat from the modules and pump;
only radiator rejection and the powered chiller remove it. Summing the battery
and coolant energy changes cancels internal heat exchange exactly.

## Electrical transients

The RC branch has capacitor energy as well as resistor heat. During a current
step, using `I²R1` for all branch input incorrectly converts stored polarization
energy immediately into heat. The implementation integrates `v_rc²/R1` exactly
over each constant-current substep.

See `IMPLEMENTATION_STATUS.md` for unresolved validation gates.
