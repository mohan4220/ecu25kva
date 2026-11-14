function names = model_list()
%MODEL_LIST  The component models, in build order. Each is generated to
%   firmware/gen/<name>/ and wrapped by firmware/core/model_glue.c.
%   Simulink: governor, rail, the two calibration tables, injector law,
%   trip decision. Stateflow: engine mode and the five guards.
names = {'ecu_gov', 'ecu_rail', 'ecu_railset', 'ecu_soi', 'ecu_injdur', 'ecu_safety', ...
         'ecu_mode', 'ecu_boostg', 'ecu_egrg', 'ecu_wifg', 'ecu_underg', 'ecu_relay'};
end
