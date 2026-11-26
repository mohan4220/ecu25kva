function mdl_ecu25kva(P)
%MDL_ECU25KVA  The whole 25 kVA ECU in one model: the project's top level.
%
%   PROJECT   buttons that generate the code, build the firmware and the
%             bootloader, flash the board, clean, run every check and
%             simulate (ecu_project.m), and the PCB selector.
%   TRIGGERS  the scheduler: initialisation, the cylinder-event interrupt
%             and the 1 ms, 20 ms, 500 ms, 1 s and 10 s tasks, as the
%             firmware runs them (Stateflow, function-call events).
%   MODEL     the ECU application. Each task holds the component models
%             themselves (Model blocks), the same models the flashed code
%             is generated from. "Set PGNs" and "SEND all PGNs" are the
%             J1939 side.
%   PLANT     simulation only: the engine and generator (mean value, the
%             constants of firmware/sim/engine.py), the fuel rail, and
%             the sensor voltages they produce.
%   SCENARIO  ignition at 0.5 s, the starter until RUN, 20 kW at 8 s, the
%             stop switch (pin 25) at 16 s. The battery voltage, the
%             coolant temperature, the 100 V boost rail and the coolant
%             level switch (pin 43) are profiles, flat by default
%             (13.5 V: an assumed charging voltage, not measured; 85 degC;
%             99.7 V; level OK). sim_ecu25kva's later runs change them,
%             and two of MODEL's stand-ins (i_valid, crank_fault), to
%             drive the protection and the fallbacks. "DSE" stands in for the panel: its Protect lamp
%             input drops the ignition, as the DSE4522 shuts the set down.
%
%   Edit the component models (ecu_*.slx) directly; press Generate code,
%   then Build. This script only lays the top level out from scratch.
m = 'ecu25kva';
mb.new(m);
set_param(m, 'StopTime', '20');
% opened from anywhere (a double-click in Explorer), the buttons still find
% ecu_project, the scripts and the tests: the model puts its folders on
% the path as it loads
set_param(m, 'PostLoadFcn', ['d = fileparts(get_param(''ecu25kva'', ''FileName'')); ' ...
    'addpath(d, fullfile(d, ''lib''), fullfile(d, ''test''));']);
S = 'single'; U8 = 'uint8';
E = engine_constants();

% ======================================================= PROJECT buttons
btn = {'Generate code', 'generate', [20 20 200 60]; ...
       'Build firmware', 'build', [220 20 400 60]; ...
       'Bootloader', 'bootloader', [420 20 600 60]; ...
       'Flash (ST-LINK)', 'flash_stlink', [620 20 800 60]; ...
       'Flash (J-Link)', 'flash_jlink', [820 20 1000 60]; ...
       'Clean project', 'clean', [20 75 200 115]; ...
       'Run all checks', 'check', [220 75 400 115]; ...
       'Simulate', 'simulate', [420 75 600 115]};
for i = 1:size(btn, 1)
    p = [m '/' strrep(btn{i, 1}, ' ', '_')];
    add_block('built-in/SubSystem', p, 'Position', btn{i, 3}, 'BackgroundColor', 'green', ...
        'ShowName', 'off', 'OpenFcn', sprintf('ecu_project(''%s'')', btn{i, 2}));
    set_param(p, 'Mask', 'on', 'MaskDisplay', sprintf('disp(''%s'')', btn{i, 1}), ...
        'MaskIconOpaque', 'opaque', 'MaskDescription', sprintf('Double-click: ecu_project(''%s'')', btn{i, 2}));
end
p = [m '/Select_PCB'];
add_block('built-in/SubSystem', p, 'Position', [620 75 800 115], 'BackgroundColor', 'gray');
set_param(p, 'Mask', 'on', 'MaskStyleString', 'popup(prototype STM32G474 rev 1|production S32K148)', ...
    'MaskVariables', 'board=&1;', 'MaskPromptString', 'PCB', ...
    'MaskValueString', 'prototype STM32G474 rev 1', 'MaskDisplay', 'disp(board)', ...
    'MaskDescription', 'The board Build and Flash work for.');
p = [m '/Version'];
add_block('built-in/SubSystem', p, 'Position', [820 75 1000 115], 'BackgroundColor', 'green', ...
    'ShowName', 'off');
h = fileread(fullfile(fileparts(mfilename('fullpath')), '..', 'firmware', 'core', 'ecu.h'));
sw = regexp(h, '#define ECU_SW_VERSION (0x[0-9A-Fa-f]+)', 'tokens', 'once');
set_param(p, 'Mask', 'on', 'MaskDisplay', ...
    sprintf('disp(''software %s  ABI %d'')', sw{1}, P.ECU_ABI_VERSION));

% ======================================================= SCENARIO
add_block('simulink/Sources/Step', [m '/ignition'], 'Time', '0.5', 'Before', '0', 'After', '1', 'SampleTime', '0.001');
add_block('simulink/Sources/Step', [m '/load_kw'], 'Time', '8', 'Before', '0', 'After', '20', 'SampleTime', '0.001');
add_block('simulink/Sources/Step', [m '/stop_sw'], 'Time', '16', 'Before', '0', 'After', '1', 'SampleTime', '0.001');
mb.b(m, 'ign_u8', 'simulink/Signal Attributes/Data Type Conversion', 'OutDataTypeStr', U8);
mb.b(m, 'stop_u8', 'simulink/Signal Attributes/Data Type Conversion', 'OutDataTypeStr', U8);
mb.l(m, 'ignition/1', 'ign_u8/1'); mb.l(m, 'stop_sw/1', 'stop_u8/1');
mb.k(m, 'i_egr', 1.5, S);
mb.k(m, 'wif', 0, U8);
mb.k(m, 'droop', 0, U8);
mb.k(m, 'r_coil', 3.75, S);                     % the metering coil the plant has (ohm)
% profiles against time (clipped at the ends); flat unless a run sets them
add_block('simulink/Sources/Digital Clock', [m '/clock'], 'SampleTime', '0.001');
add_block('simulink/Lookup Tables/1-D Lookup Table', [m '/v_bat'], ...
    'BreakpointsForDimension1', '[0 100]', 'Table', '[13.5 13.5]', 'ExtrapMethod', 'Clip', 'OutDataTypeStr', S);
add_block('simulink/Lookup Tables/1-D Lookup Table', [m '/clt_degc'], ...
    'BreakpointsForDimension1', '[0 100]', 'Table', '[85 85]', 'ExtrapMethod', 'Clip', 'OutDataTypeStr', S);
add_block('simulink/Lookup Tables/1-D Lookup Table', [m '/v_boost_rail'], ...
    'BreakpointsForDimension1', '[0 100]', 'Table', '[99.7 99.7]', 'ExtrapMethod', 'Clip', 'OutDataTypeStr', S);
mb.l(m, 'clock/1', 'v_bat/1', 'clt_degc/1', 'v_boost_rail/1');
add_block('simulink/Sources/Step', [m '/clt_low'], 'Time', '1e6', 'Before', '0', 'After', '1', 'SampleTime', '0.001');
mb.b(m, 'clt_low_u8', 'simulink/Signal Attributes/Data Type Conversion', 'OutDataTypeStr', U8);
mb.l(m, 'clt_low/1', 'clt_low_u8/1');
% DSE: the Protect lamp drops the ignition the next millisecond
mb.b(m, 'protect_z', 'simulink/Discrete/Unit Delay', 'InitialCondition', '0', 'SampleTime', '0.001');
mb.b(m, 'protect_b', 'simulink/Signal Attributes/Data Type Conversion', 'OutDataTypeStr', 'boolean');
mb.b(m, 'ign_b', 'simulink/Signal Attributes/Data Type Conversion', 'OutDataTypeStr', 'boolean');
mb.b(m, 'DSE_no_protect', 'simulink/Logic and Bit Operations/Logical Operator', 'Operator', 'NOT', 'OutDataTypeStr', 'boolean');
mb.b(m, 'DSE_ignition', 'simulink/Logic and Bit Operations/Logical Operator', 'Operator', 'AND', 'Inputs', '2', 'OutDataTypeStr', 'boolean');
mb.b(m, 'ign_dse', 'simulink/Signal Attributes/Data Type Conversion', 'OutDataTypeStr', U8);
mb.l(m, 'protect_z/1', 'protect_b/1'); mb.l(m, 'protect_b/1', 'DSE_no_protect/1');
mb.l(m, 'ign_u8/1', 'ign_b/1'); mb.l(m, 'ign_b/1', 'DSE_ignition/1'); mb.l(m, 'DSE_no_protect/1', 'DSE_ignition/2');
mb.l(m, 'DSE_ignition/1', 'ign_dse/1');

% ======================================================= TRIGGERS
ch = sfb_scheduler(m);  %#ok<NASGU>

% ======================================================= MODEL
model_block(m, P);

% ======================================================= PLANT
plant(m, E, P);

% ======================================================= wiring
for i = 1:7                                     % the events, into MODEL's first seven ports
    mb.l(m, sprintf('TRIGGERS/%d', i), sprintf('MODEL/%d', i));
end
po = @(blk, n) [blk '/' get_param([m '/' blk '/' n], 'Port')];    % a port, by its block's name
pi_ = po;
mb.l(m, po('PLANT', 'cyl_edge'), 'TRIGGERS/1');
mb.l(m, po('PLANT', 'v_sens'), pi_('MODEL', 'v_sens'));
mb.l(m, po('PLANT', 'v_5v'), pi_('MODEL', 'v_5v'));
mb.l(m, po('PLANT', 'v_bts'), pi_('MODEL', 'v_bts'));
mb.l(m, po('PLANT', 'rpm'), pi_('MODEL', 'rpm'));
mb.l(m, 'ign_dse/1', pi_('MODEL', 'ignition')); mb.l(m, 'stop_u8/1', pi_('MODEL', 'stop_sw'));
mb.l(m, 'clt_low_u8/1', pi_('MODEL', 'clt_low'));
mb.l(m, po('MODEL', 'protect'), 'protect_z/1');
mb.l(m, 'v_bat/1', pi_('PLANT', 'v_bat')); mb.l(m, 'r_coil/1', pi_('PLANT', 'r_coil')); mb.l(m, 'clt_degc/1', pi_('PLANT', 'clt_degc'));
mb.l(m, 'droop/1', pi_('MODEL', 'droop')); mb.l(m, 'v_boost_rail/1', pi_('MODEL', 'v_boost_rail'));
mb.l(m, 'i_egr/1', pi_('MODEL', 'i_egr')); mb.l(m, 'wif/1', pi_('MODEL', 'wif'));
mb.l(m, 'v_bat/1', pi_('MODEL', 'v_bat')); mb.l(m, po('PLANT', 'i_mu'), pi_('MODEL', 'i_mu'));
mb.l(m, po('MODEL', 'fuel_mg'), pi_('PLANT', 'fuel_mg'));
mb.l(m, 'load_kw/1', pi_('PLANT', 'load_kw'));
mb.l(m, po('MODEL', 'starter'), pi_('PLANT', 'starter'));
mb.l(m, po('MODEL', 'duty'), pi_('PLANT', 'duty'));

% ======================================================= logging
logs = {'rpm', po('PLANT', 'rpm'); 'rail_bar', po('PLANT', 'rail_bar'); 'i_mu', po('PLANT', 'i_mu')};
for n = {'mode', 'fuel_mg', 'duty', 'set_bar', 'gov_set', 'relay', 'afterrun', 'boost_dis', ...
         'egr_off', 'clt_c', 'oil_kpa', 'soi_deg', 'dur_us', 'eec1', 'et1_tx', 'eflp1_tx', 'hours_tx', ...
         'spd_state', 'egr_duty', 'dg_act', 'protect', 'lamps', 'mu_r', 'bts_c', 'ic1'}
    logs(end + 1, :) = {n{1}, po('MODEL', n{1})}; %#ok<AGROW>
end
logs{strcmp(logs(:, 1), 'rail_bar'), 1} = 'rail_true';      % the plant's; the ECU's is measured
logs(end + 1, :) = {'rail_bar', po('MODEL', 'rail_bar')};
for i = 1:size(logs, 1)
    add_block('simulink/Sinks/To Workspace', [m '/log_' logs{i, 1}], 'VariableName', logs{i, 1}, ...
        'SaveFormat', 'Timeseries', 'SampleTime', '0.001');
    mb.l(m, logs{i, 2}, ['log_' logs{i, 1} '/1']);
end
for n = {'fmi', 'starter'}
    if ~any(strcmp(logs(:, 1), n{1}))
        add_block('simulink/Sinks/Terminator', [m '/t_' n{1}]);
        mb.l(m, po('MODEL', n{1}), ['t_' n{1} '/1']);
    end
end
set_param(m, 'Description', ['The 25 kVA ECU: PROJECT buttons, TRIGGERS, MODEL (the component ' ...
    'models the flashed code is generated from), PLANT and SCENARIO (simulation only).']);
mb.finish(m);
end

% ----------------------------------------------------------------------
function ch = sfb_scheduler(m)
% The firmware's timing, as function-call events: SysTick every 1 ms
% (one_ms_task), the slower J1939 rates, and the crank-tooth interrupt
% reduced to one event per cylinder (cyl_event_isr) for the injection.
add_block('sflib/Chart', [m '/TRIGGERS']);
ch = sfroot().find('-isa', 'Stateflow.Chart', 'Path', [m '/TRIGGERS']);
ch.ActionLanguage = 'MATLAB';
ch.ChartUpdate = 'DISCRETE';
ch.SampleTime = '0.001';
d = Stateflow.Data(ch); d.Name = 'cyl_edge'; d.Scope = 'Input'; d.DataType = 'uint8';
sfb.local(ch, 'k', 'uint32');
names = {'initialisation', 'cyl_event_isr', 'one_ms_task', 'twenty_ms_task', ...
         'five_hundred_ms_task', 'one_sec_task', 'ten_sec_task'};
for i = 1:numel(names)
    e = Stateflow.Event(ch); e.Name = names{i}; e.Scope = 'Output'; e.Trigger = 'Function call';
end
s = sfb.state(ch, ['RUN\nentry: k = uint32(0); send(initialisation);\n' ...
    'during:\nk = k + uint32(1);\n' ...
    'if cyl_edge ~= 0, send(cyl_event_isr); end\n' ...
    'send(one_ms_task);\n' ...
    'if mod(k, uint32(20)) == 0, send(twenty_ms_task); end\n' ...
    'if mod(k, uint32(500)) == 0, send(five_hundred_ms_task); end\n' ...
    'if mod(k, uint32(1000)) == 0, send(one_sec_task); end\n' ...
    'if mod(k, uint32(10000)) == 0, send(ten_sec_task); end'], [40 40 360 220]);
sfb.def(ch, s);
end

% ----------------------------------------------------------------------
function p = fcs(parent, name)
% A function-call subsystem, empty but for its trigger port.
p = [parent '/' name];
add_block('built-in/SubSystem', p);
add_block('built-in/TriggerPort', [p '/' name '_call'], 'TriggerType', 'function-call');
end

function ref(sys, name, mdl)
add_block('simulink/Ports & Subsystems/Model', [sys '/' name], 'ModelName', mdl);
set_param([sys '/' name], 'Description', ['model: ' mdl]);
end

function inp(sys, name, type, dims)
h = mb.in(sys, name, type);
if nargin > 3, set_param(h, 'PortDimensions', num2str(dims)); end
end

% ----------------------------------------------------------------------
function model_block(m, P)
S = 'single'; U8 = 'uint8';
M = [m '/MODEL'];
add_block('built-in/SubSystem', M, 'BackgroundColor', 'cyan');

% ---------- initialisation: the end-of-line trims (gain 1, offset 0 until a record is loaded)
I = fcs(M, 'initialisation');
mb.k(I, 'gain0', ones(6, 1), S); mb.k(I, 'offset0', zeros(6, 1), S);
mb.out(I, 'gain', S); mb.out(I, 'offset', S);
mb.l(I, 'gain0/1', 'gain/1'); mb.l(I, 'offset0/1', 'offset/1');

% ---------- one_ms_task: sensors, protection, state, control, guards
T = fcs(M, 'one_ms_task');
inp(T, 'v_sens', S, 5); inp(T, 'v_5v', S); inp(T, 'gain', S, 6); inp(T, 'offset', S, 6);
inp(T, 'rpm', S); inp(T, 'ignition', U8); inp(T, 'stop_sw', U8); inp(T, 'droop', U8);
inp(T, 'v_boost_rail', S); inp(T, 'i_egr', S); inp(T, 'wif', U8);
inp(T, 'i_mu', S); inp(T, 'v_bat', S); inp(T, 'clt_low', U8); inp(T, 'v_bts', S);
outs = {'mode', U8; 'fuel_mg', S; 'duty', S; 'starter', U8; 'rail_bar', S; 'clt_c', S; ...
        'oil_kpa', S; 'fmi', U8; 'gov_set', S; 'relay', U8; 'afterrun', U8; 'boost_dis', U8; ...
        'egr_off', U8; 'set_bar', S; 'spd_state', U8; 'egr_duty', S; 'dg_act', U8; 'protect', U8; ...
        'lamps', U8; 'mu_r', S; 'bts_c', S; 'bts_fmi', U8};
for i = 1:size(outs, 1), mb.out(T, outs{i, 1}, outs{i, 2}); end
ref(T, 'sensors', 'ecu_sensors');
for b = {'mode_m', 'ecu_mode'; 'safety', 'ecu_safety'; 'gov', 'ecu_gov'; 'railset', 'ecu_railset'; ...
         'rail', 'ecu_rail'; 'boostg', 'ecu_boostg'; 'boostm', 'ecu_boostm'; 'egrg', 'ecu_egrg'; ...
         'wifg', 'ecu_wifg'; 'underg', 'ecu_underg'; 'relay_m', 'ecu_relay'; ...
         'spdst', 'ecu_spdst'; 'mucur', 'ecu_mucur'; 'egrpos', 'ecu_egrpos'; ...
         'musup', 'ecu_musup'; 'sensaux', 'ecu_sensaux'; 'lamps_m', 'ecu_lamps'; 'egrtgt', 'ecu_egrtgt'}'
    ref(T, b{1}, b{2});
end
mb.l(T, 'v_sens/1', 'sensors/1'); mb.l(T, 'v_5v/1', 'sensors/2');
mb.l(T, 'gain/1', 'sensors/3'); mb.l(T, 'offset/1', 'sensors/4');
% the sensor vectors, by channel: 1 coolant, 2 oil, 3 rail
mb.b(T, 'val_ch', 'simulink/Signal Routing/Demux', 'Outputs', '5');
mb.l(T, 'sensors/1', 'val_ch/1');
mb.l(T, 'val_ch/1', 'clt_c/1'); mb.l(T, 'val_ch/2', 'oil_kpa/1'); mb.l(T, 'val_ch/3', 'rail_bar/1');
add_block('simulink/Sinks/Terminator', [T '/t_val4']);
mb.l(T, 'val_ch/4', 't_val4/1');
mb.l(T, 'sensors/2', 'fmi/1');

% the order ecu.c sends the state machine its commands (simulation only:
% in the firmware ecu.c does this, and the chart decides the conditions)
seq = sprintf([ ...
 'function [cmd, starter] = sequencer(mode, ign, rpm, why, stop, btrip)\n' ...
 '%%#codegen\n' ...
 '%% 0 OFF, 1 WAIT, 2 CRANK, 3 RUN, 4 SHUTDOWN (mode is last tick''s)\n' ...
 'if mode ~= 4 && (btrip ~= 0 || (mode ~= 0 && (why ~= 0 || stop ~= 0)))\n' ...
 '    cmd = uint8(4);                          %% TRIP\n' ...
 'elseif mode == 1 && rpm > single(0)\n' ...
 '    cmd = uint8(2);                          %% TOOTH\n' ...
 'elseif mode == 2\n' ...
 '    cmd = uint8(3);                          %% RUN_OK\n' ...
 'else\n' ...
 '    cmd = uint8(1);                          %% TICK\n' ...
 'end\n' ...
 'starter = uint8(ign ~= 0 && (mode == 1 || mode == 2));\n']);
mfun(T, 'Sequencer', seq, containers.Map( ...
    {'mode', 'ign', 'rpm', 'why', 'stop', 'btrip', 'cmd', 'starter'}, {U8, U8, S, U8, U8, U8, U8, U8}));
mb.b(T, 'mode_z', 'simulink/Discrete/Unit Delay', 'InitialCondition', '0', 'SampleTime', '-1');
mb.l(T, 'mode_z/1', 'Sequencer/1'); mb.l(T, 'ignition/1', 'Sequencer/2'); mb.l(T, 'rpm/1', 'Sequencer/3');
mb.l(T, 'stop_sw/1', 'Sequencer/5');
mb.k(T, 'phased', 1, U8);
mb.l(T, 'Sequencer/1', 'mode_m/1'); mb.l(T, 'ignition/1', 'mode_m/2'); mb.l(T, 'phased/1', 'mode_m/3');
mb.l(T, 'rpm/1', 'mode_m/4');
mb.l(T, 'mode_m/1', 'mode/1', 'mode_z/1');
mb.l(T, 'Sequencer/2', 'starter/1');
% safety: the state before this tick, as ecu.c's check()
mb.b(T, 'was_run', 'simulink/Logic and Bit Operations/Compare To Constant', 'const', '3', 'relop', '==', 'OutDataTypeStr', U8);
mb.b(T, 'is_run', 'simulink/Logic and Bit Operations/Compare To Constant', 'const', '3', 'relop', '==', 'OutDataTypeStr', U8);
mb.l(T, 'mode_z/1', 'was_run/1'); mb.l(T, 'mode_m/1', 'is_run/1');
mb.k(T, 'crank_fault', 0, U8);
mb.l(T, 'rpm/1', 'safety/1'); mb.l(T, 'crank_fault/1', 'safety/2'); mb.l(T, 'ignition/1', 'safety/3');
mb.l(T, 'was_run/1', 'safety/4'); mb.l(T, 'safety/1', 'Sequencer/4');
% governor, reset on the tick the mode becomes RUN
mb.b(T, 'run_edge_b', 'simulink/Logic and Bit Operations/Logical Operator', 'Operator', 'AND', 'Inputs', '2', 'OutDataTypeStr', 'boolean');
mb.b(T, 'not_was', 'simulink/Logic and Bit Operations/Logical Operator', 'Operator', 'NOT', 'OutDataTypeStr', 'boolean');
mb.b(T, 'run_edge', 'simulink/Signal Attributes/Data Type Conversion', 'OutDataTypeStr', U8);
mb.l(T, 'was_run/1', 'not_was/1'); mb.l(T, 'is_run/1', 'run_edge_b/1'); mb.l(T, 'not_was/1', 'run_edge_b/2');
mb.l(T, 'run_edge_b/1', 'run_edge/1');
mb.k(T, 'FUEL_START', P.FUEL_START_MG, S);
mb.l(T, 'rpm/1', 'gov/1'); mb.l(T, 'droop/1', 'gov/2'); mb.l(T, 'run_edge/1', 'gov/3');
mb.l(T, 'FUEL_START/1', 'gov/4'); mb.l(T, 'rpm/1', 'gov/5');
% the speed states (the 20 kVA cascade's first stage): idle, operating, steady
mb.k(T, 'TARGET', P.GOV_RPM_SET, S);
mb.k(T, 'IDLE_MS', P.SPD_IDLE_MS, 'uint32');
mb.l(T, 'rpm/1', 'spdst/1'); mb.l(T, 'TARGET/1', 'spdst/2'); mb.l(T, 'is_run/1', 'spdst/3');
mb.l(T, 'IDLE_MS/1', 'spdst/4');
mb.l(T, 'spdst/1', 'gov/6'); mb.l(T, 'spdst/2', 'spd_state/1');
mb.l(T, 'gov/2', 'gov_set/1');
% fuel: RUN the governor, CRANK the start fuel, else none
mb.b(T, 'fuel', 'simulink/Signal Routing/Multiport Switch', 'Inputs', '5', 'DataPortOrder', 'Zero-based contiguous');
mb.k(T, 'NOFUEL', 0, S);
mb.l(T, 'mode_m/1', 'fuel/1'); mb.l(T, 'NOFUEL/1', 'fuel/2', 'fuel/3', 'fuel/6');
mb.l(T, 'FUEL_START/1', 'fuel/4'); mb.l(T, 'gov/1', 'fuel/5');
mb.l(T, 'fuel/1', 'fuel_mg/1', 'railset/1');
% rail: the PI from the converted rail sensor, cranking or running; else closed
mb.l(T, 'railset/1', 'rail/1', 'set_bar/1'); mb.l(T, 'val_ch/3', 'rail/2');
mb.k(T, 'rail_rst', 0, U8); mb.l(T, 'rail_rst/1', 'rail/3');
mb.b(T, 'ge_crank', 'simulink/Logic and Bit Operations/Compare To Constant', 'const', '2', 'relop', '>=', 'OutDataTypeStr', 'boolean');
mb.b(T, 'le_run', 'simulink/Logic and Bit Operations/Compare To Constant', 'const', '3', 'relop', '<=', 'OutDataTypeStr', 'boolean');
mb.b(T, 'fuelling', 'simulink/Logic and Bit Operations/Logical Operator', 'Operator', 'AND', 'Inputs', '2', 'OutDataTypeStr', 'boolean');
mb.l(T, 'mode_m/1', 'ge_crank/1', 'le_run/1');
mb.l(T, 'ge_crank/1', 'fuelling/1'); mb.l(T, 'le_run/1', 'fuelling/2');
mb.k(T, 'CLOSED', P.METER_CLOSED, S);
mb.b(T, 'duty_sw', 'simulink/Signal Routing/Switch', 'Criteria', 'u2 ~= 0');
mb.l(T, 'rail/1', 'duty_sw/1'); mb.l(T, 'fuelling/1', 'duty_sw/2'); mb.l(T, 'CLOSED/1', 'duty_sw/3');
% the metering cascade's inner loop: the command is a current. Ahead of it,
% the supervision (ecu_musup), as ecu.c: trust the reading, learn the coil,
% or fall back on it. Last tick's duty made this tick's current; the two
% diagnoses' active states are last tick's too (act_fb, below).
mb.k(T, 'i_valid', 1, U8);
mb.b(T, 'duty_z', 'simulink/Discrete/Unit Delay', 'InitialCondition', '0', 'SampleTime', '-1');
mb.b(T, 'mu_r_z', 'simulink/Discrete/Unit Delay', 'InitialCondition', mb.num(P.MU_R_NOM), 'SampleTime', '-1');
mb.b(T, 'mu_bad_z', 'simulink/Discrete/Unit Delay', 'InitialCondition', '0', 'SampleTime', '-1');
mb.l(T, 'duty_sw/1', 'musup/1'); mb.l(T, 'duty_z/1', 'musup/2'); mb.l(T, 'v_bat/1', 'musup/3');
mb.l(T, 'i_mu/1', 'musup/4'); mb.l(T, 'i_valid/1', 'musup/5');
mb.l(T, 'mu_r_z/1', 'musup/8'); mb.l(T, 'mu_bad_z/1', 'musup/9');
mb.l(T, 'musup/3', 'mu_r_z/1', 'mu_r/1'); mb.l(T, 'musup/4', 'mu_bad_z/1');
mb.l(T, 'musup/1', 'mucur/1'); mb.l(T, 'i_mu/1', 'mucur/2'); mb.l(T, 'musup/2', 'mucur/3');
mb.l(T, 'v_bat/1', 'mucur/4'); mb.l(T, 'mucur/1', 'duty/1', 'duty_z/1');
% pin 79, charge-air temperature (ecu_sensaux): IC1's SPN 105
mb.l(T, 'v_bts/1', 'sensaux/1'); mb.l(T, 'v_5v/1', 'sensaux/2');
mb.l(T, 'sensaux/1', 'bts_c/1'); mb.l(T, 'sensaux/2', 'bts_fmi/1');
% the guards
mb.b(T, 'shut', 'simulink/Logic and Bit Operations/Compare To Constant', 'const', '4', 'relop', '==', 'OutDataTypeStr', U8);
mb.l(T, 'mode_z/1', 'shut/1');
mb.l(T, 'v_boost_rail/1', 'boostg/1'); mb.l(T, 'shut/1', 'boostg/2');
mb.l(T, 'boostg/2', 'Sequencer/6'); mb.l(T, 'boostg/1', 'boost_dis/1');
mb.b(T, 'fuelling_u8', 'simulink/Signal Attributes/Data Type Conversion', 'OutDataTypeStr', U8);
mb.l(T, 'fuelling/1', 'fuelling_u8/1');
mb.l(T, 'v_boost_rail/1', 'boostm/1'); mb.l(T, 'fuelling_u8/1', 'boostm/2');
mb.l(T, 'i_egr/1', 'egrg/1'); mb.l(T, 'egrg/1', 'egr_off/1');
% EGR, the other cascade: target position -> position PID -> bridge duty.
% The target, by fuel while running (ecu.c: RUN ? gov.fuel : 0), is
% ecu_egrtgt: zeros until the emissions calibration exists.
mb.b(T, 'egr_fuel', 'simulink/Signal Routing/Switch', 'Criteria', 'u2 ~= 0');
mb.l(T, 'gov/1', 'egr_fuel/1'); mb.l(T, 'is_run/1', 'egr_fuel/2'); mb.l(T, 'NOFUEL/1', 'egr_fuel/3');
mb.l(T, 'egr_fuel/1', 'egrtgt/1');
mb.b(T, 'egr_ok', 'simulink/Logic and Bit Operations/Logical Operator', 'Operator', 'NOT', 'OutDataTypeStr', 'boolean');
mb.b(T, 'egr_en_b', 'simulink/Logic and Bit Operations/Logical Operator', 'Operator', 'AND', 'Inputs', '2', 'OutDataTypeStr', 'boolean');
mb.b(T, 'egr_en', 'simulink/Signal Attributes/Data Type Conversion', 'OutDataTypeStr', U8);
mb.l(T, 'egrg/1', 'egr_ok/1'); mb.l(T, 'is_run/1', 'egr_en_b/1'); mb.l(T, 'egr_ok/1', 'egr_en_b/2');
mb.l(T, 'egr_en_b/1', 'egr_en/1');
mb.l(T, 'egrtgt/1', 'egrpos/1'); mb.l(T, 'val_ch/5', 'egrpos/2'); mb.l(T, 'egr_en/1', 'egrpos/3');
mb.l(T, 'egrpos/1', 'egr_duty/1');
mb.l(T, 'wif/1', 'wifg/1');
mb.b(T, 'armed', 'simulink/Logic and Bit Operations/Compare To Constant', 'const', '1499', 'relop', '>=', 'OutDataTypeStr', 'boolean');
mb.b(T, 'armed_b', 'simulink/Logic and Bit Operations/Logical Operator', 'Operator', 'AND', 'Inputs', '2', 'OutDataTypeStr', 'boolean');
mb.b(T, 'is_run_b', 'simulink/Signal Attributes/Data Type Conversion', 'OutDataTypeStr', 'boolean');
mb.b(T, 'armed_run', 'simulink/Signal Attributes/Data Type Conversion', 'OutDataTypeStr', U8);
mb.l(T, 'gov/2', 'armed/1'); mb.l(T, 'is_run/1', 'is_run_b/1');
mb.l(T, 'armed/1', 'armed_b/1'); mb.l(T, 'is_run_b/1', 'armed_b/2'); mb.l(T, 'armed_b/1', 'armed_run/1');
mb.l(T, 'rpm/1', 'underg/1'); mb.l(T, 'armed_run/1', 'underg/2');
mb.b(T, 'stopped', 'simulink/Logic and Bit Operations/Compare To Constant', 'const', '1', 'relop', '<', 'OutDataTypeStr', U8);
mb.k(T, 'written', 1, U8);
mb.l(T, 'rpm/1', 'stopped/1');
mb.l(T, 'ignition/1', 'relay_m/1'); mb.l(T, 'stopped/1', 'relay_m/2'); mb.l(T, 'written/1', 'relay_m/3');
mb.l(T, 'relay_m/1', 'relay/1'); mb.l(T, 'relay_m/2', 'afterrun/1');
term = {'boostm', 1; 'boostm', 2; 'boostm', 3; 'boostm', 4; 'egrg', 2; 'wifg', 1; 'wifg', 2; ...
        'underg', 1; 'underg', 2; 'relay_m', 3};
for i = 1:size(term, 1)
    t = sprintf('term_%s_%d', term{i, 1}, term{i, 2});
    add_block('simulink/Sinks/Terminator', [T '/' t]);
    mb.l(T, sprintf('%s/%d', term{i, 1}, term{i, 2}), [t '/1']);
end

% the diagnoses and the coolant protection, as ecu.c's diagnose(): the
% 14 conditions of ecu_diag, each debounced and healed by its own ecu_deb
% on diag.c's times; the active states come back the next tick (the
% return levels of the battery and coolant). These are the models the
% flashed code is generated from. Fault 13 (110/0, coolant over 104 degC)
% is the Protect lamp, on which the DSE shuts the set down.
ref(T, 'diag', 'ecu_diag');
mb.b(T, 'fmi_sens', 'simulink/Signal Routing/Demux', 'Outputs', '5');
mb.l(T, 'sensors/2', 'fmi_sens/1');
for k = [1 2 3 5]                                  % coolant, oil, rail, EGR position: sensor good
    nm = sprintf('sens_ok%d', k);
    mb.b(T, nm, 'simulink/Logic and Bit Operations/Compare To Constant', 'const', '0', 'relop', '==', 'OutDataTypeStr', U8);
    mb.l(T, sprintf('fmi_sens/%d', k), [nm '/1']);
end
add_block('simulink/Sinks/Terminator', [T '/t_fmi_sens4']); mb.l(T, 'fmi_sens/4', 't_fmi_sens4/1');
mb.b(T, 'ign_on', 'simulink/Logic and Bit Operations/Compare To Constant', 'const', '0', 'relop', '~=', 'OutDataTypeStr', U8);
mb.l(T, 'mode_m/1', 'ign_on/1');
mb.b(T, 'act_z', 'simulink/Discrete/Unit Delay', 'InitialCondition', 'zeros(14,1)', 'SampleTime', '-1');
mb.b(T, 'act_fb', 'simulink/Signal Routing/Demux', 'Outputs', '14');
mb.l(T, 'act_z/1', 'act_fb/1');
% ecu_diag's inputs, in diag_in_t's order (i_egr: the plant's is steady, so
% it stands for ecu.c's filtered current; i_mu: always measured here)
dsrc = {'is_run/1', 'ign_on/1', 'stopped/1', 'rpm/1', 'v_bat/1', ...
        'egrpos/1', 'i_egr/1', 'val_ch/5', 'sens_ok5/1', 'egrg/1', ...
        'mucur/1', 'i_mu/1', 'i_valid/1', 'railset/1', 'val_ch/3', 'sens_ok3/1', ...
        'val_ch/2', 'sens_ok2/1', 'act_fb/10', 'act_fb/11', ...
        'val_ch/1', 'sens_ok1/1', 'clt_low/1', 'act_fb/12', 'act_fb/13'};
for k = 1:numel(dsrc), mb.l(T, dsrc{k}, sprintf('diag/%d', k)); end
mb.l(T, 'act_fb/4', 'musup/6'); mb.l(T, 'act_fb/5', 'musup/7');   % 1347/5, 1347/6
for k = [1:3 6:9 14]
    add_block('simulink/Sinks/Terminator', sprintf('%s/t_act%d', T, k));
    mb.l(T, sprintf('act_fb/%d', k), sprintf('t_act%d/1', k));
end
mb.b(T, 'cond_ch', 'simulink/Signal Routing/Demux', 'Outputs', '14');
mb.l(T, 'diag/1', 'cond_ch/1');
mb.b(T, 'act_mux', 'simulink/Signal Routing/Mux', 'Inputs', '14');
for k = 1:14
    d = sprintf('deb_%s', lower(strrep(P.dg_names{k}, 'DG_', '')));
    ref(T, d, 'ecu_deb');
    mb.k(T, [d '_ms'], P.dg_deb(k), 'uint16');
    mb.k(T, [d '_heal'], P.dg_heal(k), 'uint16');
    mb.l(T, sprintf('cond_ch/%d', k), [d '/1']);
    mb.l(T, [d '_ms/1'], [d '/2']); mb.l(T, [d '_heal/1'], [d '/3']);
    mb.l(T, [d '/1'], sprintf('act_mux/%d', k));
end
assert(isequal(P.dg_names(10:14), {'DG_BAT_HIGH', 'DG_BAT_LOW', 'DG_CLT_WARN', 'DG_CLT_STOP', 'DG_CLT_LEVEL'}), ...
    'mdl_ecu25kva: diag.h order changed: the feedback and Protect wiring above assume it');
mb.l(T, 'act_mux/1', 'act_z/1', 'dg_act/1');
% the active faults as DM1's table (in the firmware, ecu.c's fault_raise),
% and the lamps from it (ecu_lamps): Protect is what the DSE shuts down on
assert(isequal(P.dg_names{4}, 'DG_MU_OPEN') && isequal(P.dg_names{5}, 'DG_MU_OVERCUR'), ...
    'mdl_ecu25kva: diag.h order changed: the supervision wiring above assumes it');
ft = sprintf([ ...
 'function [spn, fmi, n] = table(act)\n' ...
 '%%#codegen\n' ...
 'SPN = uint32(%s); FMI = uint8(%s);\n' ...
 'spn = zeros(%d, 1, ''uint32''); fmi = zeros(%d, 1, ''uint8''); n = uint8(0);\n' ...
 'for k = int32(1):int32(14)\n' ...
 '    if act(k) ~= 0 && n < uint8(%d)\n' ...
 '        n = n + uint8(1);\n' ...
 '        spn(n) = SPN(k); fmi(n) = FMI(k);\n' ...
 '    end\n' ...
 'end\n'], mb.num(P.dg_spn), mb.num(P.dg_fmi), P.FAULTS_MAX, P.FAULTS_MAX, P.FAULTS_MAX);
mfun(T, 'fault_table', ft, containers.Map({'act', 'spn', 'fmi', 'n'}, {U8, 'uint32', U8, U8}));
mb.l(T, 'act_mux/1', 'fault_table/1');
mb.l(T, 'fault_table/1', 'lamps_m/1'); mb.l(T, 'fault_table/2', 'lamps_m/2'); mb.l(T, 'fault_table/3', 'lamps_m/3');
mb.b(T, 'protect_bit', 'simulink/Logic and Bit Operations/Bitwise Operator', 'logicop', 'AND', ...
    'UseBitMask', 'on', 'BitMask', num2str(P.LAMP_PROTECT), 'NumInputPorts', '1');
mb.b(T, 'protect_on', 'simulink/Logic and Bit Operations/Compare To Constant', 'const', '0', 'relop', '~=', 'OutDataTypeStr', U8);
mb.l(T, 'lamps_m/1', 'lamps/1', 'protect_bit/1'); mb.l(T, 'protect_bit/1', 'protect_on/1');
mb.l(T, 'protect_on/1', 'protect/1');

% ---------- cyl_event_isr: the injection for the cylinder coming up
C = fcs(M, 'cyl_event_isr');
inp(C, 'fuel_mg', S); inp(C, 'rail_bar', S);
mb.out(C, 'soi_deg', S); mb.out(C, 'dur_us', 'uint32');
ref(C, 'soi', 'ecu_soi'); ref(C, 'injdur', 'ecu_injdur');
mb.l(C, 'fuel_mg/1', 'soi/1', 'injdur/1'); mb.l(C, 'rail_bar/1', 'injdur/2');
mb.l(C, 'soi/1', 'soi_deg/1'); mb.l(C, 'injdur/1', 'dur_us/1');

% ---------- twenty_ms_task: Set PGNs (all of them), send EEC1
J = fcs(M, 'twenty_ms_task');
inp(J, 'rpm', S); inp(J, 'clt_c', S); inp(J, 'oil_kpa', S); inp(J, 'fmi', U8, 5); inp(J, 'engine_s', 'uint32');
inp(J, 'clt_low', U8); inp(J, 'bts_c', S); inp(J, 'bts_fmi', U8);
for o = {'eec1', 'et1', 'eflp1', 'hours', 'ic1'}, mb.out(J, o{1}, U8); end
ref(J, 'Set_PGNs', 'ecu_j1939');
mb.b(J, 'fmi_ch', 'simulink/Signal Routing/Demux', 'Outputs', '5');
mb.l(J, 'fmi/1', 'fmi_ch/1');
mb.b(J, 'clt_ok', 'simulink/Logic and Bit Operations/Compare To Constant', 'const', '0', 'relop', '==', 'OutDataTypeStr', U8);
mb.b(J, 'oil_ok', 'simulink/Logic and Bit Operations/Compare To Constant', 'const', '0', 'relop', '==', 'OutDataTypeStr', U8);
mb.l(J, 'fmi_ch/1', 'clt_ok/1'); mb.l(J, 'fmi_ch/2', 'oil_ok/1');
for i = 3:5
    add_block('simulink/Sinks/Terminator', sprintf('%s/t_fmi%d', J, i));
    mb.l(J, sprintf('fmi_ch/%d', i), sprintf('t_fmi%d/1', i));
end
mb.l(J, 'rpm/1', 'Set_PGNs/1'); mb.l(J, 'clt_c/1', 'Set_PGNs/2'); mb.l(J, 'clt_ok/1', 'Set_PGNs/3');
mb.l(J, 'oil_kpa/1', 'Set_PGNs/4'); mb.l(J, 'oil_ok/1', 'Set_PGNs/5'); mb.l(J, 'engine_s/1', 'Set_PGNs/6');
mb.b(J, 'bts_ok', 'simulink/Logic and Bit Operations/Compare To Constant', 'const', '0', 'relop', '==', 'OutDataTypeStr', U8);
mb.l(J, 'bts_fmi/1', 'bts_ok/1');
mb.l(J, 'clt_low/1', 'Set_PGNs/7'); mb.l(J, 'bts_c/1', 'Set_PGNs/8'); mb.l(J, 'bts_ok/1', 'Set_PGNs/9');
pg = {'eec1', 'et1', 'eflp1', 'hours', 'ic1'};
for i = 1:5, mb.l(J, sprintf('Set_PGNs/%d', i), [pg{i} '/1']); end

% ---------- SEND all PGNs: each at its own rate (500 ms EFL/P1, 1 s ET1, 10 s HOURS; EEC1 above)
send = {'five_hundred_ms_task', 'eflp1_tx'; 'one_sec_task', 'et1_tx'; 'ten_sec_task', 'hours_tx'};
for i = 1:size(send, 1)
    X = fcs(M, send{i, 1});
    inp(X, 'data', U8, 8);
    mb.out(X, send{i, 2}, U8);
    mb.l(X, 'data/1', [send{i, 2} '/1']);
end
% one_sec_task also counts engine seconds while running (the hours counter)
X = [M '/one_sec_task'];
inp(X, 'mode', U8); mb.out(X, 'engine_s', 'uint32');
mb.b(X, 'running', 'simulink/Logic and Bit Operations/Compare To Constant', 'const', '3', 'relop', '==', 'OutDataTypeStr', 'uint8');
mb.b(X, 'acc', 'simulink/Math Operations/Sum', 'Inputs', '++', 'OutDataTypeStr', 'uint32');
mb.b(X, 'acc_z', 'simulink/Discrete/Unit Delay', 'InitialCondition', '0', 'SampleTime', '-1');
mb.l(X, 'mode/1', 'running/1'); mb.l(X, 'running/1', 'acc/1'); mb.l(X, 'acc_z/1', 'acc/2');
mb.l(X, 'acc/1', 'acc_z/1', 'engine_s/1');

% ---------- MODEL's ports, and the wiring between its tasks
trig = {'initialisation', 'cyl_event_isr', 'one_ms_task', 'twenty_ms_task', ...
        'five_hundred_ms_task', 'one_sec_task', 'ten_sec_task'};
for i = 1:numel(trig)
    add_block('built-in/Inport', [M '/' trig{i} '_in']);
    add_line(M, [trig{i} '_in/1'], [trig{i} '/Trigger'], 'autorouting', 'smart');
end
mins = {'v_sens', S, 5; 'v_5v', S, 1; 'rpm', S, 1; 'ignition', U8, 1; 'stop_sw', U8, 1; ...
        'droop', U8, 1; 'v_boost_rail', S, 1; 'i_egr', S, 1; 'wif', U8, 1; 'i_mu', S, 1; 'v_bat', S, 1; ...
        'clt_low', U8, 1; 'v_bts', S, 1};
for i = 1:size(mins, 1)
    h = add_block('built-in/Inport', [M '/' mins{i, 1}]);
    set_param(h, 'OutDataTypeStr', mins{i, 2}, 'PortDimensions', num2str(mins{i, 3}));
end
mb.l(M, 'v_sens/1', 'one_ms_task/1'); mb.l(M, 'v_5v/1', 'one_ms_task/2');
mb.l(M, 'initialisation/1', 'one_ms_task/3'); mb.l(M, 'initialisation/2', 'one_ms_task/4');
mb.l(M, 'rpm/1', 'one_ms_task/5', 'twenty_ms_task/1'); mb.l(M, 'ignition/1', 'one_ms_task/6');
mb.l(M, 'stop_sw/1', 'one_ms_task/7'); mb.l(M, 'droop/1', 'one_ms_task/8');
mb.l(M, 'v_boost_rail/1', 'one_ms_task/9'); mb.l(M, 'i_egr/1', 'one_ms_task/10'); mb.l(M, 'wif/1', 'one_ms_task/11');
mb.l(M, 'i_mu/1', 'one_ms_task/12'); mb.l(M, 'v_bat/1', 'one_ms_task/13');
mb.l(M, 'clt_low/1', 'one_ms_task/14', 'twenty_ms_task/6'); mb.l(M, 'v_bts/1', 'one_ms_task/15');
% task outputs, by name
o = @(t, n) [t '/' get_param([M '/' t '/' n], 'Port')];
mb.l(M, o('one_ms_task', 'fuel_mg'), 'cyl_event_isr/1');
mb.l(M, o('one_ms_task', 'rail_bar'), 'cyl_event_isr/2');
mb.l(M, o('one_ms_task', 'clt_c'), 'twenty_ms_task/2');
mb.l(M, o('one_ms_task', 'oil_kpa'), 'twenty_ms_task/3');
mb.l(M, o('one_ms_task', 'fmi'), 'twenty_ms_task/4');
mb.l(M, o('one_ms_task', 'bts_c'), 'twenty_ms_task/7');
mb.l(M, o('one_ms_task', 'bts_fmi'), 'twenty_ms_task/8');
mb.l(M, o('one_ms_task', 'mode'), 'one_sec_task/2');
mb.l(M, o('one_sec_task', 'engine_s'), 'twenty_ms_task/5');
mb.l(M, o('twenty_ms_task', 'eflp1'), 'five_hundred_ms_task/1');
mb.l(M, o('twenty_ms_task', 'et1'), 'one_sec_task/1');
mb.l(M, o('twenty_ms_task', 'hours'), 'ten_sec_task/1');
mouts = {'one_ms_task', {'mode', 'fuel_mg', 'duty', 'starter', 'rail_bar', 'set_bar', 'gov_set', ...
         'relay', 'afterrun', 'boost_dis', 'egr_off', 'clt_c', 'oil_kpa', 'fmi', 'spd_state', 'egr_duty', ...
         'dg_act', 'protect', 'lamps', 'mu_r', 'bts_c'}; ...
         'cyl_event_isr', {'soi_deg', 'dur_us'}; 'twenty_ms_task', {'eec1', 'ic1'}; ...
         'five_hundred_ms_task', {'eflp1_tx'}; 'one_sec_task', {'et1_tx'}; 'ten_sec_task', {'hours_tx'}};
for i = 1:size(mouts, 1)
    for j = 1:numel(mouts{i, 2})
        n = mouts{i, 2}{j};
        add_block('built-in/Outport', [M '/' n]);
        mb.l(M, o(mouts{i, 1}, n), [n '/1']);
    end
end
end

% ----------------------------------------------------------------------
function plant(m, E, P)
% The engine and generator, the rail, and what the sensors read. Simulation only.
S = 'single'; U8 = 'uint8';
PL = [m '/PLANT'];
add_block('built-in/SubSystem', PL, 'BackgroundColor', 'lightBlue');
inp(PL, 'fuel_mg', S); inp(PL, 'load_kw', 'double'); inp(PL, 'starter', U8); inp(PL, 'duty', S);
inp(PL, 'v_bat', S); inp(PL, 'clt_degc', S); inp(PL, 'r_coil', S);
mb.out(PL, 'rpm', S); mb.out(PL, 'v_sens', S); mb.out(PL, 'v_5v', S); mb.out(PL, 'cyl_edge', U8);
mb.out(PL, 'rail_bar', S); mb.out(PL, 'i_mu', S); mb.out(PL, 'v_bts', S);
eng = sprintf([ ...
 'function [domega, dp] = engine(omega, p, fuel_mg, load_kw, starter, duty)\n' ...
 '%%#codegen\n' ...
 'rpm = omega * single(60 / (2*pi));\n' ...
 't_ind = single(%s) * fuel_mg * single(%d) / single(4*pi);\n' ...
 't_fric = single(10) + single(0.006) * rpm;\n' ...
 'roll = min(single(1), (rpm / single(%s))^2);\n' ...
 't_load = load_kw * single(1000) * roll / single(%s) / max(omega, single(1));\n' ...
 't_st = single(0);\n' ...
 'if starter ~= 0 && rpm < single(%s), t_st = single(%s) * (1 - rpm / single(%s)); end\n' ...
 'domega = (t_ind + t_st - t_fric - t_load) / single(%s);\n' ...
 'pump = single(%s) * rpm * (1 - duty);\n' ...
 'used = single(%s) * fuel_mg * single(%d) * rpm / single(120);\n' ...
 'dp = single(%s) * (pump - single(%s) * p - used);\n'], ...
 mb.num(E.WORK_PER_MG), E.NCYL, mb.num(E.AVR_KNEE_RPM), mb.num(E.GEN_EFF), ...
 mb.num(E.STARTER_NOLOAD), mb.num(E.STARTER_T), mb.num(E.STARTER_NOLOAD), mb.num(E.J), ...
 mb.num(E.PUMP), mb.num(E.CM3_PER_MG), E.NCYL, mb.num(E.BAR_PER_CM3), mb.num(E.LEAK));
mfun(PL, 'Engine', eng, containers.Map( ...
    {'omega', 'p', 'fuel_mg', 'load_kw', 'starter', 'duty', 'domega', 'dp'}, {S, S, S, S, U8, S, S, S}));
mb.b(PL, 'omega_i', 'simulink/Discrete/Discrete-Time Integrator', 'gainval', '1', ...
    'IntegratorMethod', 'Integration: Forward Euler', 'SampleTime', '0.001', ...
    'LimitOutput', 'on', 'LowerSaturationLimit', '0', 'UpperSaturationLimit', '400', 'OutDataTypeStr', S);
mb.b(PL, 'p_i', 'simulink/Discrete/Discrete-Time Integrator', 'gainval', '1', ...
    'IntegratorMethod', 'Integration: Forward Euler', 'SampleTime', '0.001', ...
    'LimitOutput', 'on', 'LowerSaturationLimit', '0', 'UpperSaturationLimit', mb.num(E.RELIEF), 'OutDataTypeStr', S);
mb.b(PL, 'rpm_g', 'simulink/Math Operations/Gain', 'Gain', mb.num(60 / (2*pi)));
mb.b(PL, 'load_s', 'simulink/Signal Attributes/Data Type Conversion', 'OutDataTypeStr', S);
mb.l(PL, 'load_kw/1', 'load_s/1');
a = exp(-1/40);                          % fuel delivered lags the command by about a cycle
mb.b(PL, 'lag_in', 'simulink/Math Operations/Gain', 'Gain', mb.num(1 - a));
mb.b(PL, 'lag_z', 'simulink/Discrete/Unit Delay', 'InitialCondition', '0', 'SampleTime', '0.001');
mb.b(PL, 'lag_fb', 'simulink/Math Operations/Gain', 'Gain', mb.num(a));
mb.b(PL, 'fuel_lag', 'simulink/Math Operations/Sum', 'Inputs', '++');
mb.l(PL, 'fuel_mg/1', 'lag_in/1');
mb.l(PL, 'lag_in/1', 'fuel_lag/1'); mb.l(PL, 'lag_fb/1', 'fuel_lag/2');
mb.l(PL, 'fuel_lag/1', 'lag_z/1'); mb.l(PL, 'lag_z/1', 'lag_fb/1');
mb.l(PL, 'Engine/1', 'omega_i/1'); mb.l(PL, 'Engine/2', 'p_i/1');
mb.l(PL, 'omega_i/1', 'Engine/1', 'rpm_g/1'); mb.l(PL, 'p_i/1', 'Engine/2', 'rail_bar/1');
mb.l(PL, 'fuel_lag/1', 'Engine/3'); mb.l(PL, 'load_s/1', 'Engine/4');
mb.l(PL, 'starter/1', 'Engine/5');
% the metering valve's coil: the battery into the measured coil's nominal
% 3.75 ohm (2.5-5 measured, decisions log 25), tau 3 ms; the current, as
% a fraction of full, is what closes the valve (the engine's 'duty')
coil = sprintf([ ...
 'function [i_n, frac] = coil(duty, i, v_bat, r_coil)\n' ...
 '%%#codegen\n' ...
 'i_n = i + (duty * v_bat / r_coil - i) * single(%s);\n' ...
 'frac = min(single(1), i_n / single(1.8));\n'], mb.num(1 - exp(-1/3)));
mfun(PL, 'Coil', coil, containers.Map({'duty', 'i', 'v_bat', 'r_coil', 'i_n', 'frac'}, {S, S, S, S, S, S}));
mb.b(PL, 'coil_z', 'simulink/Discrete/Unit Delay', 'InitialCondition', '0', 'SampleTime', '0.001');
mb.l(PL, 'duty/1', 'Coil/1'); mb.l(PL, 'coil_z/1', 'Coil/2'); mb.l(PL, 'v_bat/1', 'Coil/3');
mb.l(PL, 'r_coil/1', 'Coil/4');
mb.l(PL, 'Coil/1', 'coil_z/1'); mb.l(PL, 'Coil/2', 'Engine/6');
% the ADC reads the current already flowing, not the one this tick's duty will make
mb.l(PL, 'coil_z/1', 'i_mu/1');
mb.l(PL, 'rpm_g/1', 'rpm/1');
% what the sensors read: the inverse of each transfer function, 5 V supply
sv = sprintf([ ...
 'function [v, v5, vb] = volts(rpm, p, load_kw, clt)\n' ...
 '%%#codegen\n' ...
 '%% coolant through Bosch''s NTC table (in ln R) and its pull-up\n' ...
 'NT = %s; NR = %s;\n' ...
 'rn = exp(interp1(NT, log(NR), double(clt)));\n' ...
 'r = single(1 / (1 / rn + 1 / %s));          %% in parallel with NTC_LOAD\n' ...
 '%% pin 79, the charge air: the same NTC and front end; 30 degC plus 0.6 per kW\n' ...
 'rb = exp(interp1(NT, log(NR), 30 + 0.6 * double(load_kw)));\n' ...
 'rb = single(1 / (1 / rb + 1 / ' mb.num(P.NTC_LOAD) '));\n' ...
 'vb = single(5) * rb / (rb + single(' mb.num(P.NTC_PULLUP) '));\n' ...
 'v = zeros(5, 1, ''single'');\n' ...
 'v(1) = single(5) * r / (r + single(%s));\n' ...
 'lin = @(x, lo, hi) single(0.5) + single(4) * (x - lo) / (hi - lo);\n' ...
 'v(2) = lin(single(400) * rpm / single(1500), single(%s), single(%s));   %% oil, as engine.py\n' ...
 'v(3) = lin(p, single(%s), single(%s));                                  %% rail\n' ...
 'v(4) = lin(single(100) + single(100) * load_kw / single(25), single(%s), single(%s));  %% boost\n' ...
 'v(5) = single(0.5);                                                    %% EGR shut\n' ...
 'v5 = single(5);\n'], ...
 mb.num(double(P.ntc_t)), mb.num(double(P.ntc_r)), mb.num(P.NTC_LOAD), mb.num(P.NTC_PULLUP), ...
 mb.num(P.span_lo(2)), mb.num(P.span_hi(2)), mb.num(P.span_lo(3)), mb.num(P.span_hi(3)), ...
 mb.num(P.span_lo(4)), mb.num(P.span_hi(4)));
mfun(PL, 'Sensors', sv, containers.Map({'rpm', 'p', 'load_kw', 'clt', 'v', 'v5', 'vb'}, {S, S, S, S, S, S, S}));
mb.l(PL, 'rpm_g/1', 'Sensors/1'); mb.l(PL, 'p_i/1', 'Sensors/2'); mb.l(PL, 'load_s/1', 'Sensors/3');
mb.l(PL, 'clt_degc/1', 'Sensors/4');
mb.l(PL, 'Sensors/1', 'v_sens/1'); mb.l(PL, 'Sensors/2', 'v_5v/1'); mb.l(PL, 'Sensors/3', 'v_bts/1');
% one event per cylinder: the crank angle crossing each 240 degrees
ce = sprintf([ ...
 'function [edge, ang_n] = cyl(rpm, ang)\n' ...
 '%%#codegen\n' ...
 'ang_n = ang + rpm * single(6) * single(0.001);       %% degrees this ms\n' ...
 'edge = uint8(0);\n' ...
 'if ang_n >= single(240)\n' ...
 '    ang_n = ang_n - single(240);\n' ...
 '    edge = uint8(1);\n' ...
 'end\n']);
mfun(PL, 'CylEvent', ce, containers.Map({'rpm', 'ang', 'edge', 'ang_n'}, {S, S, U8, S}));
mb.b(PL, 'ang_z', 'simulink/Discrete/Unit Delay', 'InitialCondition', '0', 'SampleTime', '0.001');
mb.l(PL, 'rpm_g/1', 'CylEvent/1'); mb.l(PL, 'ang_z/1', 'CylEvent/2');
mb.l(PL, 'CylEvent/2', 'ang_z/1'); mb.l(PL, 'CylEvent/1', 'cyl_edge/1');
end

% ----------------------------------------------------------------------
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
