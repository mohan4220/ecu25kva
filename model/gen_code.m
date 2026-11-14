function gen_code(names)
%GEN_CODE  Generate C from each model into firmware/gen/<model>/.
%   gen_code() does every model; gen_code({'gov'}) just one. The shared
%   utility headers (rtwtypes.h ...) go to firmware/gen/shared/. The
%   generated files are committed, so the firmware builds without MATLAB.
here = fileparts(mfilename('fullpath'));
addpath(fullfile(here, 'lib'));
if nargin < 1, names = model_list(); end
out = fullfile(here, '..', 'firmware', 'gen');
work = fullfile(tempdir, 'ecu25kva_codegen');
if ~exist(work, 'dir'), mkdir(work); end
old = cd(work); restore = onCleanup(@() cd(old));
Simulink.fileGenControl('set', 'CacheFolder', work, 'CodeGenFolder', work, 'createDir', true);
for i = 1:numel(names)
    m = names{i};
    load_system(fullfile(here, [m '.slx']));
    slbuild(m);
    src = fullfile(work, [m '_ert_rtw']);
    dst = fullfile(out, m);
    if exist(dst, 'dir'), rmdir(dst, 's'); end
    mkdir(dst);
    for f = [dir(fullfile(src, '*.c')); dir(fullfile(src, '*.h'))]'
        if ~strcmp(f.name, 'rtmodel.h')       % only a sample main uses it
            copyfile(fullfile(src, f.name), dst);
        end
    end
    close_system(m, 0);
    fprintf('generated %s -> firmware/gen/%s\n', m, m);
end
sh = fullfile(work, 'slprj', 'ert', '_sharedutils');
dsh = fullfile(out, 'shared');
if ~exist(dsh, 'dir'), mkdir(dsh); end
for f = [dir(fullfile(sh, '*.c')); dir(fullfile(sh, '*.h'))]'
    copyfile(fullfile(sh, f.name), dsh);
end
% rtwtypes.h lands in each build folder; keep one copy in shared.
if ~exist(fullfile(dsh, 'rtwtypes.h'), 'file')
    copyfile(fullfile(work, [names{1} '_ert_rtw'], 'rtwtypes.h'), dsh);
end
for i = 1:numel(names)
    f = fullfile(out, names{i}, 'rtwtypes.h');
    if exist(f, 'file'), delete(f); end
end
end
