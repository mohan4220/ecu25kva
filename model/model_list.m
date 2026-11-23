function names = model_list()
%MODEL_LIST  The component models, in build order. Each is generated to
%   firmware/gen/<name>/ and wrapped by firmware/core/model_glue.c.
%   Simulink: governor, rail, the two calibration tables, injector law,
%   trip decision, sensor conversion (and pin 79's on its own), J1939 PGN data, the
%   diagnoses and coolant protection (ecu_diag). Stateflow: engine
%   mode, the six guards and the fault debounce (one chart, many instances).
names = {'ecu_gov', 'ecu_rail', 'ecu_railset', 'ecu_soi', 'ecu_injdur', 'ecu_safety', ...
         'ecu_mode', 'ecu_boostg', 'ecu_boostm', 'ecu_egrg', 'ecu_wifg', 'ecu_underg', 'ecu_relay', ...
         'ecu_sensors', 'ecu_sensaux', 'ecu_j1939', 'ecu_mucur', 'ecu_egrpos', 'ecu_spdst', 'ecu_deb', 'ecu_diag'};
end
