function mdl_ecu_soi(P)
%MDL_ECU_SOI  Start of injection, deg BTDC, from fuel (inject.c SOI_Q/SOI_D).
mdl_ecu_lookup('ecu_soi', P.SOI_Q, P.SOI_D, 'fuel_mg', 'soi_deg', ...
    'Start-of-injection table, from the old ECU at 1500 rpm (field evidence 2026-10-14 sec. 3b).');
end
