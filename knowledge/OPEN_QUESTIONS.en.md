[Русский](OPEN_QUESTIONS.md) | **English**

# Unverified points and further investigations

1. Actual temperature of the concealed heatsink and triac: exterior thermograms do not provide it. Direct access or a sensor and consideration of emissivity are required.
2. Extended operation with different loads, AUTO/MANUAL recovery after complete removal of all supplies, and physical verification of faults and independent shutdown. Native tests cannot substitute for a bench experiment.
3. Comparison of internal and external cold-junction compensation under the same measured terminal temperature field. The latest PID experiment used internal CJ.
4. Cause of USB influence on calibration circuits: the effect was observed, but the parasitic-current path was not measured separately. The thermocouple series did not fully distinguish contact effects from common-ground effects.
5. A full four-wire Pt100 check and uncertainty of the complete chain. The latest series used two wires and jumpers.
6. UTi260B menu heuristic: positive menu frames and negative ordinary-scene frames are needed. Four reviewed thermograms do not justify simply disabling the check throughout the live decoder.
7. Original editable EDA/CAD files are absent from the package. Update R17 in a new production revision after checking the circuit and range; old Gerber files and BOMs did not update themselves.
8. Full checking of netlist and component numbers against the PDF before automatic import of connections into the website knowledge base. Unknown connections have not been invented.
