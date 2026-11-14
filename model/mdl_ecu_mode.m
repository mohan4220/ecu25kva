function mdl_ecu_mode(P)
%MDL_ECU_MODE  The engine state machine (firmware/core/mode.c mode_cmd).
%
%     +-- Engine -------------------------------------------+
%     |  OFF --IGN_ON--> WAIT --TOOTH--> CRANK --RUN_OK--> RUN |
%     +------------------------------------------------------+
%        | TRIP (from any of them)          ^ RESET (re-enters at OFF)
%        v                                  |
%     SHUTDOWN -------------RESET-----------+
%
%   One command per call: 1 IGN_ON, 2 TOOTH, 3 RUN_OK, 4 TRIP, 5 RESET.
%   RUN_OK needs a phased crank and RUN_RPM. The crank-tooth interrupt
%   and the 1 ms tick both send commands; ecu.c acts on the entries
%   (events, governor reset, counters).
m = 'ecu_mode';
mb.new(m);
ch = sfb.chart(m, 'EngineMode', {'cmd', 'uint8'; 'phased', 'uint8'; 'rpm', 'single'}, ...
    {'mode', 'uint8'});
eng = sfb.state(ch, 'Engine', [30 40 640 190]);
off = sfb.state(eng, 'OFF\nentry: mode = uint8(0);', [60 110 110 70]);
wai = sfb.state(eng, 'WAIT\nentry: mode = uint8(1);', [210 110 110 70]);
cra = sfb.state(eng, 'CRANK\nentry: mode = uint8(2);', [360 110 120 70]);
run = sfb.state(eng, 'RUN\nentry: mode = uint8(3);', [520 110 110 70]);
shd = sfb.state(ch, 'SHUTDOWN\nentry: mode = uint8(4);', [270 300 160 70]);
sfb.def(ch, eng);
sfb.def(eng, off);
sfb.tr(eng, off, wai, '[cmd == 1]', 1, 3, 9);
sfb.tr(eng, wai, cra, '[cmd == 2]', 1, 3, 9);
sfb.tr(eng, cra, run, sprintf('[cmd == 3 && phased ~= 0 && rpm >= single(%s)]', mb.num(P.RUN_RPM)), 1, 3, 9);
sfb.tr(ch, eng, shd, '[cmd == 4]', 1, 5, 1);
sfb.tr(ch, eng, eng, '[cmd == 5]', 2, 10, 11);
sfb.tr(ch, shd, eng, '[cmd == 5]', 1, 11, 7);
set_param(m, 'Description', 'Engine state machine. Source of truth for firmware/gen/ecu_mode.');
mb.finish(m);
end
