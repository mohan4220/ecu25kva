function names = model_list()
%MODEL_LIST  The component models, in build order. Each is generated to
%   firmware/gen/<name>/ and wrapped by firmware/core/model_glue.c.
%   Simulink: governor, rail, the two calibration tables, injector law,
%   trip decision, sensor conversion, J1939 PGN data. Stateflow: engine
%   mode and the six guards.
names = {'ecu_gov', 'ecu_rail', 'ecu_railset', 'ecu_soi', 'ecu_injdur', 'ecu_safety', ...
         'ecu_mode', 'ecu_boostg', 'ecu_boostm', 'ecu_egrg', 'ecu_wifg', 'ecu_underg', 'ecu_relay', ...
         'ecu_sensors', 'ecu_j1939'};
end
