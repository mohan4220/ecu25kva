function mdl_ecu_egrtgt(P)
%MDL_ECU_EGRTGT  EGR target position from fuel (actuate.c EGR_Q/EGR_T).
%   Zeros (no EGR) until the emissions calibration exists; the table is
%   read from the C, so a calibration there reaches the model on build_all.
mdl_ecu_lookup('ecu_egrtgt', P.EGR_Q, P.EGR_T, 'fuel_mg', 'target_pct', ...
    'EGR target position by fuel, percent open. Placeholder zeros until the emissions calibration.');
end
