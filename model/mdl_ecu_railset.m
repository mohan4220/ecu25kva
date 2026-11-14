function mdl_ecu_railset(P)
%MDL_ECU_RAILSET  Rail-pressure setpoint from fuel (rail.c RAIL_Q/RAIL_P).
mdl_ecu_lookup('ecu_railset', P.RAIL_Q, P.RAIL_P, 'fuel_mg', 'set_bar', ...
    'Rail setpoint table, from the old ECU at 1500 rpm (field evidence 2026-10-14 sec. 3c).');
end
