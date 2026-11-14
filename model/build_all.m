function build_all(names)
%BUILD_ALL  Build every model (.slx) in model/ from its script.
%   The .slx files are outputs: edit mdl_<name>.m, not the model, then
%   run build_all and gen_code. Constants come from the C (ecu_params).
here = fileparts(mfilename('fullpath'));
addpath(here, fullfile(here, 'lib'));
P = ecu_params();
if nargin < 1, names = [model_list(), {'ecu_app'}]; end
for i = 1:numel(names)
    if exist(['mdl_' names{i}], 'file')
        feval(['mdl_' names{i}], P);
        fprintf('built model/%s.slx\n', names{i});
    end
end
end
