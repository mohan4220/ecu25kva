function P = ecu_params()
%ECU_PARAMS  Every constant the models use, read from the firmware's C.
%   The C headers and tables are the single source: nothing here is typed
%   twice, so a calibration change in firmware/core reaches the models on
%   the next build_all. #define NAME value[f] lines and
%   "static const float NAME[] = { ... };" tables are read.
here = fileparts(mfilename('fullpath'));
core = fullfile(here, '..', 'firmware', 'core');
P = struct();
for f = {'govern.h', 'rail.h', 'inject.h', 'safety.h', 'ecu.h', 'crank.h', 'mode.h', 'actuate.h'}
    txt = fileread(fullfile(core, f{1}));
    tok = regexp(txt, '#define\s+([A-Z][A-Z0-9_]*)\s+([-+]?[0-9.]+(?:[eE][-+]?\d+)?)[fFuU]*(?=\s|$)', 'tokens', 'lineanchors');
    for k = 1:numel(tok)
        P.(tok{k}{1}) = str2double(tok{k}{2});
    end
end
for f = {'rail.c', 'inject.c'}
    txt = fileread(fullfile(core, f{1}));
    tok = regexp(txt, 'static const float\s+([A-Z_]+)\[\]\s*=\s*\{([^}]*)\}', 'tokens');
    for k = 1:numel(tok)
        v = regexprep(tok{k}{2}, '[fF]', '');
        P.(tok{k}{1}) = str2num(['[' v ']']); %#ok<ST2NM>
    end
end
% The sensor tables and constants (sensors.c / sensors.h), lowercase in C
txt = fileread(fullfile(core, 'sensors.c'));
tok = regexp(txt, '(?:static\s+)?const\s+(?:float|uint32_t)\s+(\w+)\[[^\]]*\]\s*=\s*\{([^}]*)\}', 'tokens');
for k = 1:numel(tok)
    v = regexprep(tok{k}{2}, '[fFuU](?=[\s,]|$)', '');
    P.(tok{k}{1}) = str2num(['[' v ']']); %#ok<ST2NM>
end
for f = {'sensors.c', 'sensors.h', 'j1939.h'}
    txt = fileread(fullfile(core, f{1}));
    tok = regexp(txt, '#define\s+([A-Z][A-Z0-9_]*)\s+([-+]?[0-9.]+(?:[eE][-+]?\d+)?)[fFuU]*(?=\s|$)', 'tokens', 'lineanchors');
    for k = 1:numel(tok)
        P.(tok{k}{1}) = str2double(tok{k}{2});
    end
end
% Derived in C by expressions, not plain numbers.
P.METER_CLOSED = 1 - P.METER_NC;                       % METER_NC ? 0 : 1
P.RAIL_DUTY_LIMP = P.METER_NC * P.RAIL_OPEN_LIMP + (1 - P.METER_NC) * (1 - P.RAIL_OPEN_LIMP);
P.DT = 0.001;                                          % every caller's dt_s
need = {'GOV_RPM_SET', 'GOV_DROOP', 'FUEL_MAX_MG', 'FUEL_RATED_MG', 'GOV_KP', ...
        'GOV_KI', 'GOV_RAMP_RPM_S', 'RAIL_KP', 'RAIL_KI', 'RAIL_Q', 'RAIL_P', ...
        'SOI_Q', 'SOI_D', 'INJ_DEAD_US', 'INJ_K', 'INJ_RAIL_MIN', 'OVERSPEED_RPM', ...
        'BOOST_OV_V', 'BOOST_OV_MS', 'EGR_STALL_A', 'EGR_STALL_MS', 'EGR_COOL_MS', ...
        'EGR_STALL_TRIES', 'WIF_MS', 'UNDERSPEED_RPM', 'UNDERSPEED_CLEAR_RPM', ...
        'UNDERSPEED_MS', 'UNDERSPEED_CLEAR_MS', 'AFTERRUN_MAX_MS', 'FUEL_START_MG', 'RUN_RPM', 'BOOST_HIGH_V', 'BOOST_HIGH_MS', 'BOOST_LOW_V', 'BOOST_LOW_MS', ...
        'sens_default', 'sens_v_lo', 'span_lo', 'span_hi', 'SENS_V_HI', 'SENS_FAULT_MS', ...
        'NTC_R25', 'NTC_BETA', 'NTC_PULLUP', 'GOV_IDLE_RPM', 'SPD_BAND_RPM', 'SPD_STEADY_MS', ...
        'MU_R_NOM', 'MU_I_FULL', 'MU_V_FULL', 'MU_V_NOM', 'MU_VBAT_MIN', 'MU_VBAT_MAX', 'MU_KP', 'MU_KI', 'MU_INTEG_MAX', ...
        'EGR_KP', 'EGR_KI', 'EGR_KD', 'EGR_D_ALPHA', 'EGR_DUTY_MAX', 'EGR_CLOSED_PCT'};
miss = need(~isfield(P, need));
assert(isempty(miss), 'ecu_params: not found in the C: %s', strjoin(miss, ', '));
end
