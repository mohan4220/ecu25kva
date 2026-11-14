function mdl_ecu_mode(P)
%MDL_ECU_MODE  The engine state machine (firmware/core/mode.c mode_cmd).
%
%     +-- Engine --------------------------------------------------+
%     |  OFF --TICK, ignition--> WAIT --TOOTH--> CRANK --RUN_OK--> RUN |
%     +-------------------------------------------------------------+
%        | TRIP (from any of them)              ^ RESET, or an ignition
%        v                                      | cycle (re-enters at OFF)
%     SHUTDOWN ---------------------------------+
%
%   One command per call: 1 TICK (every 1 ms), 2 TOOTH, 3 RUN_OK, 4 TRIP,
%   5 RESET. The chart owns its conditions: the ignition for OFF -> WAIT,
%   a phased crank at RUN_RPM for CRANK -> RUN, and the ignition cycle that
%   ends SHUTDOWN (ignition low for IGN_OFF_MS with the engine stopped,
%   then on; a contact bounce does nothing). ecu.c acts on the entries
%   (events, the governor reset, the reset of everything else at OFF).
m = 'ecu_mode';
mb.new(m);
ch = sfb.chart(m, 'EngineMode', {'cmd', 'uint8'; 'ignition', 'uint8'; 'phased', 'uint8'; 'rpm', 'single'}, ...
    {'mode', 'uint8'});
sfb.local(ch, 'low', 'uint16');
ign = sprintf('uint16(%s)', mb.num(P.IGN_OFF_MS));
eng = sfb.state(ch, 'Engine', [30 40 700 190]);
off = sfb.state(eng, 'OFF\nentry: mode = uint8(0);', [60 110 110 70]);
wai = sfb.state(eng, 'WAIT\nentry: mode = uint8(1);', [230 110 110 70]);
cra = sfb.state(eng, 'CRANK\nentry: mode = uint8(2);', [400 110 120 70]);
run = sfb.state(eng, 'RUN\nentry: mode = uint8(3);', [580 110 110 70]);
shd = sfb.state(ch, sprintf(['SHUTDOWN\nentry: mode = uint8(4); low = uint16(0);\n' ...
    'during:\nif cmd == 1\n    if ignition ~= 0\n        low = uint16(0);\n' ...
    '    elseif rpm == 0\n        low = min(low + 1, %s);\n    else\n        low = uint16(0);\n' ...
    '    end\nend'], ign), [250 300 260 200]);
sfb.def(ch, eng, '{low = uint16(0);}');
sfb.def(eng, off);
sfb.tr(eng, off, wai, '[cmd == 1 && ignition ~= 0]', 1, 3, 9);
sfb.tr(eng, wai, cra, '[cmd == 2]', 1, 3, 9);
sfb.tr(eng, cra, run, sprintf('[cmd == 3 && phased ~= 0 && rpm >= single(%s)]', mb.num(P.RUN_RPM)), 1, 3, 9);
sfb.tr(ch, eng, shd, '[cmd == 4]', 1, 5, 1);
sfb.tr(ch, eng, eng, '[cmd == 5]', 2, 10, 11);
sfb.tr(ch, shd, eng, '[cmd == 5]', 1, 11, 7);
sfb.tr(ch, shd, eng, sprintf('[cmd == 1 && ignition ~= 0 && low >= %s]', ign), 2, 1, 5);
set_param(m, 'Description', 'Engine state machine. Source of truth for firmware/gen/ecu_mode.');
mb.finish(m);
end
