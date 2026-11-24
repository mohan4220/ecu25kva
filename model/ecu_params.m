function P = ecu_params()
%ECU_PARAMS  Every constant the models use, read from the firmware's C.
%   The C headers and tables are the single source: nothing here is typed
%   twice, so a calibration change in firmware/core reaches the models on
%   the next build_all. #define NAME value[f] lines and
%   "static const float NAME[] = { ... };" tables are read.
here = fileparts(mfilename('fullpath'));
core = fullfile(here, '..', 'firmware', 'core');
P = struct();
for f = {'govern.h', 'rail.h', 'inject.h', 'safety.h', 'ecu.h', 'crank.h', 'mode.h', 'actuate.h', 'diag.h'}
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
    v = regexprep(v, '\s+', ' ');                       % one row, even if the C wraps
    P.(tok{k}{1}) = str2num(['[' v ']']); %#ok<ST2NM>
end
for f = {'sensors.c', 'sensors.h', 'j1939.h'}
    txt = fileread(fullfile(core, f{1}));
    tok = regexp(txt, '#define\s+([A-Z][A-Z0-9_]*)\s+([-+]?[0-9.]+(?:[eE][-+]?\d+)?)[fFuU]*(?=\s|$)', 'tokens', 'lineanchors');
    for k = 1:numel(tok)
        P.(tok{k}{1}) = str2double(tok{k}{2});
    end
end
% The crank decoder's fault codes, an enum in crank.h: checked, not assumed
txt = fileread(fullfile(core, 'crank.h'));
assert(~isempty(regexp(txt, 'enum\s*\{\s*CRANK_F_NONE\s*,\s*CRANK_F_GAP\s*,\s*CRANK_F_TIMEOUT\s*\}', 'once')), ...
    'ecu_params: crank.h fault enum changed');
P.CRANK_F_GAP = 1; P.CRANK_F_TIMEOUT = 2;
% Hexadecimal #defines (the DM1 lamp bits in j1939.h)
for f = {'j1939.h', 'safety.h'}
    txt = fileread(fullfile(core, f{1}));
    tok = regexp(txt, '#define\s+([A-Z][A-Z0-9_]*)\s+0[xX]([0-9A-Fa-f]+)[uU]*(?=\s|$)', 'tokens', 'lineanchors');
    for k = 1:numel(tok)
        P.(tok{k}{1}) = hex2dec(tok{k}{2});
    end
end
% The diagnoses' debounce and healing times: diag.c's table, in diag.h's
% enum order (the order ecu_diag's 14 conditions come out in).
txt = fileread(fullfile(core, 'diag.h'));
en = regexp(txt, 'enum\s*\{(.*?)\<DG_N\>', 'tokens', 'once');
dgn = regexp(en{1}, '\<(DG_[A-Z_]+)\s*,', 'tokens');
dgn = cellfun(@(c) c{1}, dgn, 'UniformOutput', false);
txt = fileread(fullfile(core, 'diag.c'));
tok = regexp(txt, '\[(DG_[A-Z_]+)\]\s*=\s*\{\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\}', 'tokens');
assert(numel(dgn) == 14 && numel(tok) == 14, 'ecu_params: diag.h/diag.c: expected 14 diagnoses');
P.dg_names = dgn;
P.dg_deb = zeros(1, 14); P.dg_heal = zeros(1, 14); P.dg_spn = zeros(1, 14); P.dg_fmi = zeros(1, 14);
for k = 1:14
    t = tok{strcmp(cellfun(@(c) c{1}, tok, 'UniformOutput', false), dgn{k})};
    P.dg_spn(k) = str2double(t{2}); P.dg_fmi(k) = str2double(t{3});
    P.dg_deb(k) = str2double(t{4}); P.dg_heal(k) = str2double(t{5});
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
        'ntc_t', 'ntc_r', 'NTC_PULLUP', 'NTC_LOAD', 'SENS_AUX_DEFAULT', 'GOV_IDLE_RPM', 'SPD_BAND_RPM', 'SPD_STEADY_MS', ...
        'MU_R_NOM', 'MU_I_FULL', 'MU_V_FULL', 'MU_V_NOM', 'MU_VBAT_MIN', 'MU_VBAT_MAX', 'MU_KP', 'MU_KI', 'MU_INTEG_MAX', ...
        'EGR_KP', 'EGR_KI', 'EGR_KD', 'EGR_D_ALPHA', 'EGR_DUTY_MAX', 'EGR_CLOSED_PCT', ...
        'DG_EGR_DRIVE', 'DG_EGR_OPEN_A', 'DG_EGR_COAST', 'DG_EGR_HARD', 'DG_EGR_POS_PCT', ...
        'DG_BAT_EGR_LO', 'DG_BAT_EGR_HI', 'DG_MU_EXPECT_A', 'DG_MU_R_HI', 'DG_MU_OPEN_A', 'DG_MU_MAX_A', ...
        'DG_RAIL_DEV_BAR', 'DG_RAIL_DEV_FRAC', 'DG_SPD_HIGH_RPM', 'DG_OIL_RUN_KPA', 'DG_OIL_STOP_KPA', ...
        'DG_BAT_HIGH_V', 'DG_BAT_HIGH_RET_V', 'DG_BAT_LOW_V', 'DG_BAT_LOW_RET_V', 'DG_BAT_MEASURED_V', ...
        'DG_CLT_WARN_C', 'DG_CLT_WARN_RET_C', 'DG_CLT_STOP_C', 'DG_CLT_STOP_RET_C', ...
        'MU_R_LO', 'MU_R_HI', 'MU_R_LEARN_A', 'MU_R_ALPHA', 'MU_DISTRUST_MS', ...
        'LAMP_RED', 'LAMP_AMBER', 'LAMP_PROTECT', 'SPN_SPEED', 'SPN_POS', 'SPN_CLT', ...
        'SPN_BOOST_RAIL', 'FMI_HIGH_SEVERE', 'FAULTS_MAX', ...
        'CRANK_TEETH', 'CRANK_WIN', 'CRANK_TIMEOUT_US', 'CRANK_CAM_TOL', 'CRANK_CAM_MISS'};
miss = need(~isfield(P, need));
assert(isempty(miss), 'ecu_params: not found in the C: %s', strjoin(miss, ', '));
end
