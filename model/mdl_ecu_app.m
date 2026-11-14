function mdl_ecu_app(P)
%MDL_ECU_APP  The whole application, closed loop with an engine, to simulate.
%
%   Every block marked "model:" is the component model itself, referenced
%   (the same model the firmware's code is generated from). Around them:
%     - Sequencer: the order ecu.c drives the state machine in (one
%       command per tick: TRIP > RESET > IGN_ON > TOOTH > RUN_OK). In the
%       firmware ecu.c does this; here it is simulation-only.
%     - Engine: a mean-value model with the constants of
%       firmware/sim/engine.py (inertia, work per mg, friction, the
%       generator's load and voltage roll-off, the starter, the rail
%       pump, leak and relief). Tooth timing and per-cylinder injection
%       are the platform's job and are not modelled here.
%     - Scenario: ignition on at 0.5 s, the starter turns until RUN,
%       20 kW on at 8 s, the stop switch (pin 25) pressed at 16 s.
%   Run it with model/test/sim_ecu_app.m, which checks and plots it.
m = 'ecu_app';
mb.new(m);
set_param(m, 'StopTime', '20');
S = 'single'; U8 = 'uint8';
E = engine_constants();

% ---------- scenario
add_block('simulink/Sources/Step', [m '/ignition'], 'Time', '0.5', 'Before', '0', 'After', '1', 'SampleTime', '0.001');
add_block('simulink/Sources/Step', [m '/load_kw'], 'Time', '8', 'Before', '0', 'After', '20', 'SampleTime', '0.001');
add_block('simulink/Sources/Step', [m '/stop_sw'], 'Time', '16', 'Before', '0', 'After', '1', 'SampleTime', '0.001');
mb.k(m, 'v_boost_rail', 99.7, S);
mb.k(m, 'i_egr', 1.5, S);
mb.k(m, 'wif', 0, U8);
mb.b(m, 'ign_u8', 'simulink/Signal Attributes/Data Type Conversion', 'OutDataTypeStr', U8);
mb.b(m, 'stop_u8', 'simulink/Signal Attributes/Data Type Conversion', 'OutDataTypeStr', U8);
mb.l(m, 'ignition/1', 'ign_u8/1'); mb.l(m, 'stop_sw/1', 'stop_u8/1');

% ---------- the component models
ref = @(name, mdl) add_block('simulink/Ports & Subsystems/Model', [m '/' name], 'ModelName', mdl);
ref('mode', 'ecu_mode'); ref('safety', 'ecu_safety'); ref('gov', 'ecu_gov');
ref('railset', 'ecu_railset'); ref('rail', 'ecu_rail'); ref('boostg', 'ecu_boostg');
ref('egrg', 'ecu_egrg'); ref('wifg', 'ecu_wifg'); ref('underg', 'ecu_underg'); ref('relay', 'ecu_relay');
for b = {'mode', 'safety', 'gov', 'railset', 'rail', 'boostg', 'egrg', 'wifg', 'underg', 'relay'}
    set_param([m '/' b{1}], 'Description', ['model: ' get_param([m '/' b{1}], 'ModelName')]);
end

% ---------- sequencer (ecu.c's job in the firmware)
seq = sprintf([ ...
 'function [cmd, starter, running] = sequencer(mode, ign, rpm, why, stop, btrip)\n' ...
 '%%#codegen\n' ...
 '%% ECU states: 0 OFF, 1 WAIT, 2 CRANK, 3 RUN, 4 SHUTDOWN (mode is last tick''s).\n' ...
 'persistent low_ms\n' ...
 'if isempty(low_ms), low_ms = uint16(0); end\n' ...
 'cycled = ign ~= 0 && low_ms >= uint16(%s);    %% ignition low that long, stopped, then on\n' ...
 'if ign ~= 0\n' ...
 '    low_ms = uint16(0);\n' ...
 'elseif rpm < single(1)\n' ...
 '    low_ms = min(low_ms + 1, uint16(10000));\n' ...
 'else\n' ...
 '    low_ms = uint16(0);\n' ...
 'end\n' ...
 'cmd = uint8(0);\n' ...
 '%% ecu.c: OFF returns before check(), but the boost guard runs first\n' ...
 'if mode ~= 4 && (btrip ~= 0 || (mode ~= 0 && (why ~= 0 || stop ~= 0)))\n' ...
 '    cmd = uint8(4);                          %% TRIP\n' ...
 'elseif mode == 4 && cycled\n' ...
 '    cmd = uint8(5);                          %% RESET: a real ignition cycle\n' ...
 'elseif mode == 0 && ign ~= 0\n' ...
 '    cmd = uint8(1);                          %% IGN_ON\n' ...
 'elseif mode == 1 && rpm > single(0)\n' ...
 '    cmd = uint8(2);                          %% TOOTH\n' ...
 'elseif mode == 2\n' ...
 '    cmd = uint8(3);                          %% RUN_OK (the chart checks phase and speed)\n' ...
 'end\n' ...
 'starter = uint8(ign ~= 0 && (mode == 1 || mode == 2));\n' ...
 'running = uint8(mode == 3);\n'], mb.num(P.IGN_OFF_MS));
mfun(m, 'Sequencer', seq, containers.Map( ...
    {'mode', 'ign', 'rpm', 'why', 'stop', 'btrip', 'cmd', 'starter', 'running'}, ...
    {U8, U8, S, U8, U8, U8, U8, U8, U8}));
mb.b(m, 'mode_z', 'simulink/Discrete/Unit Delay', 'InitialCondition', '0', 'SampleTime', '0.001');
mb.l(m, 'mode/1', 'mode_z/1');
mb.l(m, 'mode_z/1', 'Sequencer/1');
mb.l(m, 'ign_u8/1', 'Sequencer/2');
mb.l(m, 'stop_u8/1', 'Sequencer/5');
mb.k(m, 'phased', 1, U8);
mb.l(m, 'Sequencer/1', 'mode/1'); mb.l(m, 'phased/1', 'mode/2');

% governor reset on the tick the mode becomes RUN (ecu.c: gov_reset on entry)
mb.b(m, 'is_run', 'simulink/Logic and Bit Operations/Compare To Constant', 'const', '3', 'relop', '==', 'OutDataTypeStr', 'uint8');
mb.b(m, 'was_run', 'simulink/Logic and Bit Operations/Compare To Constant', 'const', '3', 'relop', '==', 'OutDataTypeStr', 'uint8');
mb.b(m, 'run_edge_b', 'simulink/Logic and Bit Operations/Logical Operator', 'Operator', 'AND', 'Inputs', '2', 'OutDataTypeStr', 'boolean');
mb.b(m, 'run_edge', 'simulink/Signal Attributes/Data Type Conversion', 'OutDataTypeStr', U8);
mb.l(m, 'run_edge_b/1', 'run_edge/1');
mb.b(m, 'not_was', 'simulink/Logic and Bit Operations/Logical Operator', 'Operator', 'NOT', 'OutDataTypeStr', 'boolean');
mb.l(m, 'mode/1', 'is_run/1'); mb.l(m, 'mode_z/1', 'was_run/1');
mb.l(m, 'was_run/1', 'not_was/1');
mb.l(m, 'is_run/1', 'run_edge_b/1'); mb.l(m, 'not_was/1', 'run_edge_b/2');
mb.k(m, 'FUEL_START', P.FUEL_START_MG, S);

% ---------- engine (mean value)
eng = sprintf([ ...
 'function [domega, dp, v_rail_p] = engine(omega, p, fuel_mg, load_kw, starter, duty)\n' ...
 '%%#codegen\n' ...
 'rpm = omega * single(60 / (2*pi));\n' ...
 't_ind = single(%s) * fuel_mg * single(%d) / single(4*pi);   %% indicated, N m\n' ...
 't_fric = single(10) + single(0.006) * rpm;\n' ...
 'roll = min(single(1), (rpm / single(%s))^2);                %% the AVR''s roll-off\n' ...
 't_load = load_kw * single(1000) * roll / single(%s) / max(omega, single(1));\n' ...
 't_st = single(0);\n' ...
 'if starter ~= 0 && rpm < single(%s), t_st = single(%s) * (1 - rpm / single(%s)); end\n' ...
 'domega = (t_ind + t_st - t_fric - t_load) / single(%s);\n' ...
 'pump = single(%s) * rpm * (1 - duty);                     %% normally open: duty 1 = no flow\n' ...
 'used = single(%s) * fuel_mg * single(%d) * rpm / single(120);\n' ...
 'dp = single(%s) * (pump - single(%s) * p - used);\n' ...
 'v_rail_p = p;\n'], ...
 mb.num(E.WORK_PER_MG), E.NCYL, mb.num(E.AVR_KNEE_RPM), mb.num(E.GEN_EFF), ...
 mb.num(E.STARTER_NOLOAD), mb.num(E.STARTER_T), mb.num(E.STARTER_NOLOAD), mb.num(E.J), ...
 mb.num(E.PUMP), mb.num(E.CM3_PER_MG), E.NCYL, mb.num(E.BAR_PER_CM3), mb.num(E.LEAK));
mfun(m, 'Engine', eng, containers.Map( ...
    {'omega', 'p', 'fuel_mg', 'load_kw', 'starter', 'duty', 'domega', 'dp', 'v_rail_p'}, ...
    {S, S, S, S, U8, S, S, S, S}));
mb.b(m, 'omega_i', 'simulink/Discrete/Discrete-Time Integrator', 'gainval', '1', ...
    'IntegratorMethod', 'Integration: Forward Euler', 'SampleTime', '0.001', ...
    'LimitOutput', 'on', 'LowerSaturationLimit', '0', 'UpperSaturationLimit', '400', 'OutDataTypeStr', S);
mb.b(m, 'p_i', 'simulink/Discrete/Discrete-Time Integrator', 'gainval', '1', ...
    'IntegratorMethod', 'Integration: Forward Euler', 'SampleTime', '0.001', ...
    'LimitOutput', 'on', 'LowerSaturationLimit', '0', 'UpperSaturationLimit', mb.num(E.RELIEF), 'OutDataTypeStr', S);
mb.b(m, 'rpm', 'simulink/Math Operations/Gain', 'Gain', mb.num(60 / (2*pi)));
mb.b(m, 'load_s', 'simulink/Signal Attributes/Data Type Conversion', 'OutDataTypeStr', S);
mb.l(m, 'load_kw/1', 'load_s/1');
% fuel delivered lags the command by about a cycle
a = exp(-1/40);
mb.b(m, 'lag_in', 'simulink/Math Operations/Gain', 'Gain', mb.num(1 - a));
mb.b(m, 'lag_z', 'simulink/Discrete/Unit Delay', 'InitialCondition', '0', 'SampleTime', '0.001');
mb.b(m, 'lag_fb', 'simulink/Math Operations/Gain', 'Gain', mb.num(a));
mb.b(m, 'fuel_lag', 'simulink/Math Operations/Sum', 'Inputs', '++');
mb.l(m, 'lag_in/1', 'fuel_lag/1'); mb.l(m, 'lag_fb/1', 'fuel_lag/2');
mb.l(m, 'fuel_lag/1', 'lag_z/1'); mb.l(m, 'lag_z/1', 'lag_fb/1');
mb.l(m, 'Engine/1', 'omega_i/1'); mb.l(m, 'Engine/2', 'p_i/1');
mb.l(m, 'omega_i/1', 'Engine/1', 'rpm/1'); mb.l(m, 'p_i/1', 'Engine/2');
mb.l(m, 'fuel_lag/1', 'Engine/3'); mb.l(m, 'load_s/1', 'Engine/4');
mb.l(m, 'Sequencer/2', 'Engine/5');

% speed into the sequencer, safety, governor, underspeed
mb.l(m, 'rpm/1', 'Sequencer/3', 'mode/3', 'safety/1', 'gov/1', 'underg/1');
mb.k(m, 'crank_fault', 0, U8);
mb.l(m, 'crank_fault/1', 'safety/2'); mb.l(m, 'ign_u8/1', 'safety/3');
mb.l(m, 'was_run/1', 'safety/4');                % the state before this tick, as ecu.c's check()
mb.l(m, 'safety/1', 'Sequencer/4');

% governor: droop off, reset at RUN entry with the start fuel and speed
mb.k(m, 'droop', 0, U8);
mb.l(m, 'droop/1', 'gov/2'); mb.l(m, 'run_edge/1', 'gov/3');
mb.l(m, 'FUEL_START/1', 'gov/4'); mb.l(m, 'rpm/1', 'gov/5');

% fuel: RUN -> governor, CRANK -> start fuel, else 0 (ecu.c fuel_mg)
mb.b(m, 'fuel', 'simulink/Signal Routing/Multiport Switch', 'Inputs', '5', 'DataPortOrder', 'Zero-based contiguous');
mb.k(m, 'NOFUEL', 0, S);
mb.l(m, 'mode/1', 'fuel/1');
mb.l(m, 'NOFUEL/1', 'fuel/2', 'fuel/3', 'fuel/6');
mb.l(m, 'FUEL_START/1', 'fuel/4'); mb.l(m, 'gov/1', 'fuel/5');
mb.l(m, 'fuel/1', 'lag_in/1', 'railset/1');

% rail: PI while cranking or running, else the valve closed
mb.l(m, 'railset/1', 'rail/1'); mb.l(m, 'p_i/1', 'rail/2');
mb.k(m, 'rail_rst', 0, U8);
mb.l(m, 'rail_rst/1', 'rail/3');
mb.b(m, 'ge_crank', 'simulink/Logic and Bit Operations/Compare To Constant', 'const', '2', 'relop', '>=', 'OutDataTypeStr', 'boolean');
mb.b(m, 'le_run', 'simulink/Logic and Bit Operations/Compare To Constant', 'const', '3', 'relop', '<=', 'OutDataTypeStr', 'boolean');
mb.b(m, 'fuelling', 'simulink/Logic and Bit Operations/Logical Operator', 'Operator', 'AND', 'Inputs', '2', 'OutDataTypeStr', 'boolean');
mb.l(m, 'ge_crank/1', 'fuelling/1'); mb.l(m, 'le_run/1', 'fuelling/2');
mb.k(m, 'CLOSED', P.METER_CLOSED, S);
mb.b(m, 'duty', 'simulink/Signal Routing/Switch', 'Criteria', 'u2 ~= 0');
mb.l(m, 'mode/1', 'ge_crank/1', 'le_run/1');
mb.l(m, 'rail/1', 'duty/1'); mb.l(m, 'fuelling/1', 'duty/2'); mb.l(m, 'CLOSED/1', 'duty/3');
mb.l(m, 'duty/1', 'Engine/6');

% the guards
mb.b(m, 'shut', 'simulink/Logic and Bit Operations/Compare To Constant', 'const', '4', 'relop', '==', 'OutDataTypeStr', 'uint8');
mb.l(m, 'mode_z/1', 'shut/1');
mb.l(m, 'v_boost_rail/1', 'boostg/1'); mb.l(m, 'shut/1', 'boostg/2');
mb.l(m, 'boostg/2', 'Sequencer/6');
mb.l(m, 'i_egr/1', 'egrg/1');
mb.l(m, 'wif/1', 'wifg/1');
mb.b(m, 'armed', 'simulink/Logic and Bit Operations/Compare To Constant', 'const', '1499', 'relop', '>=', 'OutDataTypeStr', 'uint8');
mb.b(m, 'armed_b', 'simulink/Logic and Bit Operations/Logical Operator', 'Operator', 'AND', 'Inputs', '2', 'OutDataTypeStr', 'boolean');
mb.b(m, 'armed_run', 'simulink/Signal Attributes/Data Type Conversion', 'OutDataTypeStr', U8);
mb.l(m, 'armed_b/1', 'armed_run/1');
mb.l(m, 'gov/2', 'armed/1'); mb.l(m, 'armed/1', 'armed_b/1'); mb.l(m, 'is_run/1', 'armed_b/2');
mb.l(m, 'armed_run/1', 'underg/2');
mb.b(m, 'stopped', 'simulink/Logic and Bit Operations/Compare To Constant', 'const', '1', 'relop', '<', 'OutDataTypeStr', 'uint8');
mb.k(m, 'written', 1, U8);
mb.l(m, 'rpm/1', 'stopped/1');
mb.l(m, 'ign_u8/1', 'relay/1'); mb.l(m, 'stopped/1', 'relay/2'); mb.l(m, 'written/1', 'relay/3');

% ---------- logging
logs = {'rpm', 'rpm/1'; 'mode', 'mode/1'; 'fuel_mg', 'fuel/1'; 'rail_bar', 'p_i/1'; ...
        'set_bar', 'railset/1'; 'duty', 'duty/1'; 'gov_set', 'gov/2'; 'relay', 'relay/1'; ...
        'afterrun', 'relay/2'; 'boost_dis', 'boostg/1'; 'egr_off', 'egrg/1'; ...
        'under_raise', 'underg/1'; 'cmd', 'Sequencer/1'};
for i = 1:size(logs, 1)
    add_block('simulink/Sinks/To Workspace', [m '/log_' logs{i, 1}], 'VariableName', logs{i, 1}, ...
        'SaveFormat', 'Timeseries', 'SampleTime', '0.001');
    mb.l(m, logs{i, 2}, ['log_' logs{i, 1} '/1']);
end
% unused outputs end in terminators, so the model updates without warnings
term = {'Sequencer', 3; 'egrg', 2; 'wifg', 1; 'wifg', 2; 'underg', 2; 'relay', 3};
for i = 1:size(term, 1)
    t = sprintf('term_%s_%d', term{i, 1}, term{i, 2});
    add_block('simulink/Sinks/Terminator', [m '/' t]);
    mb.l(m, sprintf('%s/%d', term{i, 1}, term{i, 2}), [t '/1']);
end
set_param(m, 'Description', ['The ECU application, closed loop. Components are the models the ' ...
    'firmware code is generated from; the sequencer and engine are simulation-only.']);
mb.finish(m);
end

function E = engine_constants()
% firmware/sim/engine.py's constants, read from the file.
here = fileparts(mfilename('fullpath'));
txt = fileread(fullfile(here, '..', 'firmware', 'sim', 'engine.py'));
names = {'J', 'WORK_PER_MG', 'GEN_EFF', 'AVR_KNEE_RPM', 'BAR_PER_CM3', 'LEAK', 'RELIEF', 'CM3_PER_MG'};
for i = 1:numel(names)
    t = regexp(txt, ['(?m)^' names{i} '\s*=\s*([0-9.eE+-]+)'], 'tokens', 'once');
    E.(names{i}) = str2double(t{1});
end
t = regexp(txt, '(?m)^STARTER_T, STARTER_NOLOAD = ([0-9.]+), ([0-9.]+)', 'tokens', 'once');
E.STARTER_T = str2double(t{1}); E.STARTER_NOLOAD = str2double(t{2});
t = regexp(txt, '(?m)^PUMP = ([0-9.]+) / ([0-9.]+)', 'tokens', 'once');
E.PUMP = str2double(t{1}) / str2double(t{2});
E.NCYL = 3;
end
