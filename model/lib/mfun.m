function mfun(m, name, script, types)
%MFUN  A MATLAB Function block from source text. types: a containers.Map
%   of port name -> data type, applied to its inputs and outputs.
add_block('simulink/User-Defined Functions/MATLAB Function', [m '/' name]);
rt = sfroot();
ch = rt.find('-isa', 'Stateflow.EMChart', 'Path', [m '/' name]);
ch.Script = script;
for d = [ch.Inputs(:); ch.Outputs(:)]'
    if isKey(types, d.Name)
        d.DataType = types(d.Name);
    end
end
end
