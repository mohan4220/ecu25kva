function mdl_ecu_deb(~)
%MDL_ECU_DEB  A fault's debounce and healing (firmware/core/mode.c
%   deb_step, decisions log 24). One chart, many instances: every
%   diagnosis in diag.h steps its own. CLEAR until the condition has held
%   deb_ms ticks, then ACTIVE until it has been absent heal_ms ticks
%   (0: at once); a tick the other way restarts the count. The times are
%   inputs, so one generated function serves every fault.
m = 'ecu_deb';
mb.new(m);
U8 = 'uint8'; U16 = 'uint16';
ch = sfb.chart(m, 'Debounce', {'cond', U8; 'deb_ms', U16; 'heal_ms', U16}, {'act', U8});
sfb.local(ch, 'n', U16);
clr = sfb.state(ch, ['CLEAR\nentry: act = uint8(0);\n' ...
    'during: if cond ~= 0, n = n + uint16(1); else, n = uint16(0); end'], [40 60 300 90]);
act = sfb.state(ch, ['ACTIVE\nentry: act = uint8(1);\n' ...
    'during: if cond == 0, n = n + uint16(1); else, n = uint16(0); end'], [460 60 300 90]);
sfb.def(ch, clr, '{n = uint16(0); act = uint8(0);}');
sfb.tr(ch, clr, act, '[cond ~= 0 && n + uint16(1) >= deb_ms]{n = uint16(0);}', 1, 2, 10);
sfb.tr(ch, act, clr, '[cond == 0 && n + uint16(1) >= heal_ms]{n = uint16(0);}', 1, 8, 4);
set_param(m, 'Description', 'Fault debounce and healing. Source of truth for firmware/gen/ecu_deb.');
mb.finish(m);
end
