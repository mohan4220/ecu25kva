classdef sfb
%SFB  Helpers for building Stateflow charts from scripts.
%   Charts use MATLAB as the action language and explicit transition
%   order, so the evaluation order is what the script says, not what the
%   layout happens to imply.
methods (Static)
    function ch = chart(m, name, ins, outs)
        % A chart block wired to root ports. ins/outs: {name, type; ...}.
        add_block('sflib/Chart', [m '/' name]);
        ch = sfroot().find('-isa', 'Stateflow.Chart', 'Path', [m '/' name]);
        ch.ActionLanguage = 'MATLAB';
        ch.ExecuteAtInitialization = true;
        ch.ChartUpdate = 'DISCRETE';
        ch.SampleTime = '0.001';
        for i = 1:size(ins, 1)
            d = Stateflow.Data(ch);
            d.Name = ins{i, 1}; d.Scope = 'Input'; d.DataType = ins{i, 2};
            mb.in(m, ins{i, 1}, ins{i, 2});
        end
        for i = 1:size(outs, 1)
            d = Stateflow.Data(ch);
            d.Name = outs{i, 1}; d.Scope = 'Output'; d.DataType = outs{i, 2};
            mb.out(m, outs{i, 1}, outs{i, 2});
        end
        for i = 1:size(ins, 1)
            add_line(m, [ins{i, 1} '/1'], sprintf('%s/%d', name, i), 'autorouting', 'smart');
        end
        for i = 1:size(outs, 1)
            add_line(m, sprintf('%s/%d', name, i), [outs{i, 1} '/1'], 'autorouting', 'smart');
        end
    end

    function d = local(ch, name, type)
        d = Stateflow.Data(ch);
        d.Name = name; d.Scope = 'Local'; d.DataType = type;
    end

    function s = state(parent, label, pos)
        % label: 'NAME\nentry: ...\nduring: ...' (sprintf escapes applied)
        s = Stateflow.State(parent);
        s.LabelString = sprintf(label);
        s.Position = pos;
    end

    function t = tr(parent, src, dst, label, order, so, dO)
        t = Stateflow.Transition(parent);
        t.Source = src; t.Destination = dst;
        if nargin > 5, t.SourceOClock = so; t.DestinationOClock = dO; end
        t.LabelString = label;
        if nargin > 4 && ~isempty(order), t.ExecutionOrder = order; end
    end

    function t = def(parent, dst, label)
        % The default transition into dst, drawn from above it.
        t = Stateflow.Transition(parent);
        t.Destination = dst;
        t.DestinationOClock = 0;
        p = dst.Position;
        t.SourceEndpoint = [p(1) + p(3)/2, p(2) - 25];
        t.MidPoint = [p(1) + p(3)/2, p(2) - 12];
        if nargin > 2, t.LabelString = label; end
    end
end
end
