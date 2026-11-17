function mdl_ecu_spdst(P)
%MDL_ECU_SPDST  The speed states (firmware/core/mode.c spdst_step): the
%   "engine states -> RPM setpoint" stage of the 20 kVA set's cascade
%   (decisions log 23). OFF until RUN; IDLE holds the idle speed for
%   idle_ms (0: none); OPERATING ramps to and regulates the rated
%   setpoint; STEADY once within SPD_BAND_RPM for SPD_STEADY_MS, back to
%   OPERATING beyond twice the band. e = |rpm - target| comes in from
%   outside the chart.
m = 'ecu_spdst';
mb.new(m);
S = 'single'; U8 = 'uint8';
mb.in(m, 'rpm', S); mb.in(m, 'target', S);
mb.b(m, 'err', 'simulink/Math Operations/Sum', 'Inputs', '+-');
mb.b(m, 'abs_e', 'simulink/Math Operations/Abs');
mb.l(m, 'rpm/1', 'err/1'); mb.l(m, 'target/1', 'err/2'); mb.l(m, 'err/1', 'abs_e/1');
ch = sfb.chart(m, 'SpeedStates', {'running', U8; 'idle_ms', 'uint32'}, {'idle', U8; 'state', U8});
d = Stateflow.Data(ch); d.Name = 'e'; d.Scope = 'Input'; d.DataType = S;
add_line(m, 'abs_e/1', 'SpeedStates/3', 'autorouting', 'smart');
sfb.local(ch, 'n', 'uint32');
band = mb.num(P.SPD_BAND_RPM); band2 = mb.num(2 * P.SPD_BAND_RPM); steady = mb.num(P.SPD_STEADY_MS);
off = sfb.state(ch, 'OFF\nentry: idle = uint8(0); state = uint8(0);', [40 40 220 60]);
idl = sfb.state(ch, 'IDLE\nentry: idle = uint8(1); state = uint8(1);\nduring: n = n + uint32(1);', [400 40 240 80]);
opr = sfb.state(ch, sprintf(['OPERATING\nentry: idle = uint8(0); state = uint8(2);\n' ...
    'during: if e <= single(%s), n = n + uint32(1); else, n = uint32(0); end'], band), [400 240 320 90]);
std = sfb.state(ch, 'STEADY\nentry: idle = uint8(0); state = uint8(3);', [40 260 220 60]);
sfb.def(ch, off, '{n = uint32(0); idle = uint8(0); state = uint8(0);}');
sfb.tr(ch, off, idl, '[running ~= 0 && idle_ms > uint32(0)]{n = uint32(0);}', 1, 3, 9);
sfb.tr(ch, off, opr, '[running ~= 0]{n = uint32(0);}', 2, 5, 10);
sfb.tr(ch, idl, off, '[running == 0]{n = uint32(0);}', 1, 8, 4);
sfb.tr(ch, idl, opr, '[n + uint32(1) >= idle_ms]{n = uint32(0);}', 2, 6, 12);
sfb.tr(ch, opr, off, '[running == 0]{n = uint32(0);}', 1, 10, 4);
sfb.tr(ch, opr, std, sprintf('[e <= single(%s) && n + uint32(1) >= uint32(%s)]{n = uint32(0);}', band, steady), 2, 9, 3);
sfb.tr(ch, std, off, '[running == 0]{n = uint32(0);}', 1, 12, 6);
sfb.tr(ch, std, opr, sprintf('[e > single(%s)]{n = uint32(0);}', band2), 2, 2, 8);
set_param(m, 'Description', 'Speed states. Source of truth for firmware/gen/ecu_spdst.');
mb.finish(m);
end
