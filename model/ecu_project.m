function ok = ecu_project(action, varargin)
%ECU_PROJECT  What the buttons on ecu25kva.slx do. Each is also a command:
%
%   ecu_project generate      C from every component model, into firmware/gen
%   ecu_project build         generate, then build the firmware images and check them
%   ecu_project bootloader    build, then flash the bootloader and the application (SWD)
%   ecu_project flash_stlink  flash the application over SWD with an ST-LINK
%   ecu_project flash_jlink   the same with a SEGGER J-Link
%   ecu_project clean         delete everything generated that is not committed
%   ecu_project check         ./verify.sh: every check in the project
%   ecu_project simulate      run ecu25kva closed loop and check it
%
%   The application flashed is the MODEL build (app_model_*): the code
%   generated from these models, with the hand-written C only where the
%   models stop (crank decoding, the protocols, storage, the drivers).
%   Errors go to the command window and, in the desktop, a dialog.
here = fileparts(mfilename('fullpath'));
root = fileparts(here);
addpath(here, fullfile(here, 'lib'), fullfile(here, 'test'));
ok = false;
try
    switch action
        case 'generate'
            generate();
        case 'build'
            check_board();
            generate();
            build(root);
        case 'bootloader'
            check_board();
            generate();
            build(root);
            flash(root, 'stlink', {'boot.hex', 'app_model_signed.hex'});
        case 'flash_stlink'
            check_board();
            flash(root, 'stlink', {'app_model_signed.hex'});
        case 'flash_jlink'
            check_board();
            flash(root, 'jlink', {'app_model_signed.hex'});
        case 'clean'
            clean(root, here);
        case 'check'
            run_cmd(root, sprintf('"%s" verify.sh', bash()), 'verify.sh');
        case 'simulate'
            sim_ecu25kva();
        otherwise
            error('ecu_project:action', 'unknown action "%s"', action);
    end
    ok = true;
    say(sprintf('ecu_project %s: done', action), false);
catch e
    say(sprintf('ecu_project %s FAILED:\n%s', action, e.message), true);
    if nargout == 0 && ~usejava('desktop')
        rethrow(e);
    end
end
end

% ----------------------------------------------------------------------
function generate()
names = model_list();
for i = 1:numel(names)
    fprintf('generating %s\n', names{i});
end
gen_code(names);
end

function build(root)
py = python(root);
run_cmd(root, sprintf('"%s" firmware/stm32/build.py --check', py), 'firmware build');
run_cmd(root, sprintf('"%s" firmware/stm32/test_image.py', py), 'image checks');
end

function check_board()
b = 'prototype STM32G474 rev 1';
if bdIsLoaded('ecu25kva')
    b = get_param('ecu25kva/Select_PCB', 'board');
end
if ~startsWith(b, 'prototype')
    error('ecu_project:board', ['%s: its chip layer is not written yet (firmware guide ' ...
        'sec. 14). Only the prototype STM32G474 can be built and flashed.'], b);
end
end

function flash(root, probe, files)
out = fullfile(root, 'firmware', 'stm32', 'build');
for i = 1:numel(files)
    if ~exist(fullfile(out, files{i}), 'file')
        error('ecu_project:flash', '%s is not built: press Build firmware first', files{i});
    end
end
switch probe
    case 'stlink'
        cli = find_tool({'STM32_Programmer_CLI', ...
            'C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe'});
        if ~isempty(cli)
            args = sprintf(' -w "%s"', strjoin(fullfile(out, files), '" -w "'));
            run_cmd(root, sprintf('"%s" -c port=SWD mode=UR%s -v -rst', cli, args), 'ST-LINK flash');
            return
        end
        ocd = find_tool({'openocd'});
        if isempty(ocd)
            error('ecu_project:tool', ['no ST-LINK tool found: install STM32CubeProgrammer ' ...
                '(STM32_Programmer_CLI) or OpenOCD, or put it on PATH']);
        end
        prog = sprintf('-c "program {%s} verify" ', strrep(fullfile(out, files), '\', '/'));
        run_cmd(root, sprintf('"%s" -f interface/stlink.cfg -f target/stm32g4x.cfg %s-c "reset run" -c "exit"', ...
            ocd, [prog{:}]), 'OpenOCD flash');
    case 'jlink'
        jl = find_tool({'JLink', 'JLink.exe', 'C:\Program Files\SEGGER\JLink\JLink.exe'});
        if isempty(jl)
            error('ecu_project:tool', 'no J-Link Commander found: install the SEGGER J-Link software');
        end
        scr = [tempname '.jlink'];
        lines = [{'r', 'h'}, cellfun(@(f) ['loadfile ' fullfile(out, f)], files, 'UniformOutput', false), ...
                 {'r', 'g', 'exit'}];
        fid = fopen(scr, 'w'); fprintf(fid, '%s\n', lines{:}); fclose(fid);
        run_cmd(root, sprintf('"%s" -device STM32G474VE -if SWD -speed 4000 -autoconnect 1 -CommanderScript "%s"', ...
            jl, scr), 'J-Link flash');
end
end

function clean(root, here)
targets = {fullfile(root, 'firmware', 'stm32', 'build'), fullfile(here, 'slprj'), ...
           fullfile(tempdir, 'ecu25kva_codegen')};
for i = 1:numel(targets)
    if exist(targets{i}, 'dir')
        rmdir(targets{i}, 's');
        fprintf('removed %s\n', targets{i});
    end
end
% the generated C in firmware/gen is committed (the firmware builds
% without MATLAB), so clean leaves it; Generate code replaces it
end

% ----------------------------------------------------------------------
function run_cmd(root, cmd, what)
fprintf('> %s\n', cmd);
old = cd(root); back = onCleanup(@() cd(old));
setenv('PYTHONUTF8', '1');
[st, out] = system(cmd);
fprintf('%s', out);
if st ~= 0
    lines = strsplit(strtrim(out), newline);
    tail = strjoin(lines(max(1, end - 14):end), newline);
    error('ecu_project:step', '%s failed (exit %d):\n%s', what, st, tail);
end
end

function p = python(root)
for c = {fullfile(root, '.venv', 'Scripts', 'python.exe'), fullfile(root, '.venv', 'bin', 'python')}
    if exist(c{1}, 'file'), p = c{1}; return; end
end
error('ecu_project:python', 'no .venv: see README.md, "If .venv is missing"');
end

function b = bash()
for c = {'C:\Program Files\Git\bin\bash.exe', '/bin/bash', '/usr/bin/bash'}
    if exist(c{1}, 'file'), b = c{1}; return; end
end
b = 'bash';
end

function p = find_tool(names)
p = '';
for i = 1:numel(names)
    if exist(names{i}, 'file') == 2 && contains(names{i}, filesep)
        p = names{i}; return
    end
    if ispc, [st, out] = system(['where ' names{i}]); else, [st, out] = system(['command -v ' names{i}]); end
    if st == 0
        p = strtrim(strtok(out, newline)); return
    end
end
end

function say(msg, bad)
fprintf('%s\n', msg);
if usejava('desktop')
    if bad, errordlg(msg, 'ecu25kva'); else, msgbox(msg, 'ecu25kva'); end
end
end
