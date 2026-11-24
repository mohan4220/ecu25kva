function sweep_sim_diags()
%SWEEP_SIM_DIAGS  Both closed-loop runs with strict run-time checks; list
%   every warning Simulink records, grouped by identifier and block.
here = fileparts(fileparts(mfilename('fullpath')));
addpath(here, fullfile(here, 'lib'), fullfile(here, 'test'));
load_system(fullfile(here, 'ecu25kva.slx'));
in1 = Simulink.SimulationInput('ecu25kva');
for p = {'IntegerOverflowMsg', 'IntegerSaturationMsg', 'ArrayBoundsChecking', 'SignalRangeChecking', ...
         'ParameterPrecisionLossMsg', 'ParameterDowncastMsg', 'UnconnectedInputMsg', 'UnconnectedOutputMsg'}
    in1 = in1.setModelParameter(p{1}, 'warning');
end
in2 = in1.setModelParameter('StopTime', '25');
in2 = in2.setBlockParameter('ecu25kva/stop_sw', 'Time', '1e6');
in2 = in2.setBlockParameter('ecu25kva/v_bat', 'BreakpointsForDimension1', '[0 4 4.001 100]', ...
                            'ecu25kva/v_bat', 'Table', '[13.5 13.5 9.2 9.2]');
in2 = in2.setBlockParameter('ecu25kva/clt_low', 'Time', '5');
in2 = in2.setBlockParameter('ecu25kva/clt_degc', 'BreakpointsForDimension1', '[0 9 15 100]', ...
                            'ecu25kva/clt_degc', 'Table', '[85 85 106 106]');
runs = {in1, in2};
for r = 1:2
    out = sim(runs{r});
    w = out.SimulationMetadata.ExecutionInfo.WarningDiagnostics;
    ids = {};
    for k = 1:numel(w)
        d = w(k).Diagnostic;
        msg = regexprep(d.message, '<[^>]*>', '');
        blk = regexp(msg, '''(ecu[^'']*)''', 'tokens', 'once');
        if isempty(blk), blk = {'-'}; end
        ids{end + 1} = sprintf('%s | %s', d.identifier, blk{1}); %#ok<AGROW>
    end
    [u, ~, j] = unique(ids);
    fprintf('run %d: %d warnings, %d kinds\n', r, numel(w), numel(u));
    for k = 1:numel(u)
        fprintf('  %3d  %s\n', sum(j == k), u{k});
    end
end
close_system('ecu25kva', 0);
end
