# Unconfirmed points and further investigations

[Русский](OPEN_QUESTIONS.md) | **English**

1. Actual temperature of the concealed heatsink and triac: external thermograms do not provide it. Direct access/a sensor and emissivity assessment are required.
2. Extended operation with different loads, AUTO/MANUAL restoration after completely removing all supplies, and physical checks of faults and independent isolation. Native tests do not replace a bench experiment.
3. Compare internal and external cold junctions with the same measured terminal temperature field. The latest PID experiment used internal CJ.
4. Cause of USB influence in calibration circuits: the effect was observed, but the parasitic-current path was not measured separately. In the thermocouple series, contact quality was not fully separated from common-ground effects.
5. A full four-wire Pt100 check and uncertainty of the entire chain. The latest series used two wires and jumpers.
6. UTi260B menu heuristic: positive menu frames and negative ordinary-scene frames are needed. Four reviewed thermograms do not justify simply disabling this check throughout the live decoder.
7. Original editable EDA/CAD files are absent from the package. Update R17 in a new production revision only after verifying the circuit and range; old Gerbers/BOMs have not updated themselves.
8. Full netlist/component-number comparison with the PDF before automatically importing connections into the website knowledge base. Unknown connections have not been invented.
