function sweep_models()
%SWEEP_MODELS  Compile every model with strict diagnostics and report every
%   warning and error Simulink raises; then run the top model's two runs
%   with run-time integer-overflow and array-bounds checking on. A
%   diagnostic sweep, not a pass/fail gate: it lists what Simulink sees.
here = fileparts(fileparts(mfilename('fullpath')));
addpath(here, fullfile(here, 'lib'), fullfile(here, 'test'));
strict = {'UnconnectedInputMsg', 'warning'; 'UnconnectedOutputMsg', 'warning'; ...
          'UnconnectedLineMsg', 'warning'; 'IntegerOverflowMsg', 'warning'; ...
          'IntegerSaturationMsg', 'warning'; 'ParameterPrecisionLossMsg', 'warning'; ...
          'ParameterDowncastMsg', 'warning'; 'ParameterOverflowMsg', 'error'; ...
          'AlgebraicLoopMsg', 'warning'; 'ArrayBoundsChecking', 'warning'; ...
          'SignalRangeChecking', 'warning'; 'UnderSpecifiedDataTypeMsg', 'warning'; ...
          'FixptConstUnderflowMsg', 'warning'; 'FixptConstOverflowMsg', 'warning'};
names = [model_list(), {'ecu25kva'}];
for i = 1:numel(names)
    m = names{i};
    load_system(fullfile(here, [m '.slx']));
    for k = 1:size(strict, 1)
        try, set_param(m, strict{k, 1}, strict{k, 2}); catch, end
    end
    txt = '';
    try
        txt = evalc('set_param(m, ''SimulationCommand'', ''update'')');
    catch e
        txt = [txt sprintf('ERROR: %s', e.message)];
    end
    report(m, 'update', txt);
    close_system(m, 0);
end
% the two closed-loop runs, with run-time checks
load_system(fullfile(here, 'ecu25kva.slx'));
for k = 1:size(strict, 1)
    try, set_param('ecu25kva', strict{k, 1}, strict{k, 2}); catch, end
end
in1 = Simulink.SimulationInput('ecu25kva');
in2 = in1.setModelParameter('StopTime', '25');
in2 = in2.setBlockParameter('ecu25kva/stop_sw', 'Time', '1e6');
in2 = in2.setBlockParameter('ecu25kva/v_bat', 'BreakpointsForDimension1', '[0 4 4.001 100]', ...
                            'ecu25kva/v_bat', 'Table', '[13.5 13.5 9.2 9.2]');
in2 = in2.setBlockParameter('ecu25kva/clt_low', 'Time', '5');
in2 = in2.setBlockParameter('ecu25kva/clt_degc', 'BreakpointsForDimension1', '[0 9 15 100]', ...
                            'ecu25kva/clt_degc', 'Table', '[85 85 106 106]');
for r = {in1, in2}
    txt = '';
    try
        txt = evalc('sim(r{1});');
    catch e
        txt = sprintf('ERROR: %s', e.message);
    end
    report('ecu25kva', 'simulate', txt);
end
close_system('ecu25kva', 0);
end

function report(m, what, txt)
lines = strsplit(txt, newline);
keep = lines(~cellfun(@isempty, regexp(lines, 'Warning|ERROR|Error|overflow|saturat|out of bounds|algebraic|unconnected|not connected|precision', 'once', 'ignorecase')));
if isempty(keep)
    fprintf('%-12s %-9s clean\n', m, what);
else
    fprintf('%-12s %-9s %d message(s)\n', m, what, numel(keep));
    for j = 1:min(numel(keep), 12)
        fprintf('    %s\n', strtrim(keep{j}));
    end
end
end
