classdef mb
%MB  Small helpers for building models from scripts.
methods (Static)
    function new(m)
        % A fresh model with the project's code-generation settings.
        if bdIsLoaded(m), close_system(m, 0); end
        f = fullfile(mb.dir(), [m '.slx']);
        if exist(f, 'file'), delete(f); end
        new_system(m);
        mb.config(m);
    end

    function config(m)
        set_param(m, 'SolverType', 'Fixed-step', 'Solver', 'FixedStepDiscrete', ...
            'FixedStep', '0.001', 'StopTime', '10', ...
            'SystemTargetFile', 'ert.tlc', 'TargetLang', 'C', ...
            'ProdHWDeviceType', 'ARM Compatible->ARM Cortex-M', ...
            'GenCodeOnly', 'on', 'GenerateReport', 'off', ...
            'CodeInterfacePackaging', 'Reusable function', ...
            'RootIOFormat', 'Individual arguments', ...
            'DefaultParameterBehavior', 'Inlined', ...
            'DefaultUnderspecifiedDataType', 'single', ...
            'GenerateSampleERTMain', 'off', 'IncludeMdlTerminateFcn', 'off', ...
            'SupportNonFinite', 'off', 'MatFileLogging', 'off', ...
            'TargetLangStandard', 'C99 (ISO)', ...
            'SaveFormat', 'Dataset', 'SignalLogging', 'on', ...
            'UtilityFuncGeneration', 'Shared location');
    end

    function h = in(m, name, type)
        h = add_block('simulink/Sources/In1', [m '/' name], 'OutDataTypeStr', type);
    end

    function h = out(m, name, type)
        h = add_block('simulink/Sinks/Out1', [m '/' name], 'OutDataTypeStr', type);
    end

    function h = b(m, name, lib, varargin)
        h = add_block(lib, [m '/' name], varargin{:});
    end

    function k(m, name, value, type)
        % A constant block, typed.
        add_block('simulink/Sources/Constant', [m '/' name], ...
            'Value', mb.num(value), 'OutDataTypeStr', type);
    end

    function l(m, varargin)
        % l(m, 'a/1', 'b/1', 'c/2', ...): one line from the first port to each of the others.
        src = varargin{1};
        for i = 2:numel(varargin)
            add_line(m, src, varargin{i}, 'autorouting', 'smart');
        end
    end

    function s = num(v)
        s = mat2str(v, 9);
    end

    function d = dir()
        d = fileparts(fileparts(mfilename('fullpath')));
    end

    function finish(m)
        Simulink.BlockDiagram.arrangeSystem(m);
        save_system(m, fullfile(mb.dir(), [m '.slx']));
    end
end
end
