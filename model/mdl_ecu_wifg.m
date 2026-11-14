function mdl_ecu_wifg(P)
%MDL_ECU_WIFG  Water-in-fuel debounce (mode.c wifg_step), WIF_MS each way.
%   DRYING -> DRY (drop) and WETTING -> WET (raise) once the input has
%   held for WIF_MS; any change of the input restarts the count.
m = 'ecu_wifg';
mb.new(m);
ch = sfb.chart(m, 'WaterInFuel', {'wif', 'uint8'}, {'raise', 'uint8'; 'drop', 'uint8'});
sfb.local(ch, 'n', 'uint16');
ms = mb.num(P.WIF_MS);
dg = sfb.state(ch, 'DRYING\nentry: raise = uint8(0); drop = uint8(0);\nduring: n = n + 1;', [40 60 200 80]);
dr = sfb.state(ch, 'DRY\nentry: raise = uint8(0); drop = uint8(1);', [40 260 200 70]);
wg = sfb.state(ch, 'WETTING\nentry: raise = uint8(0); drop = uint8(0);\nduring: n = n + 1;', [400 60 200 80]);
we = sfb.state(ch, 'WET\nentry: raise = uint8(1); drop = uint8(0);', [400 260 200 70]);
sfb.def(ch, dg, '{n = uint16(0); raise = uint8(0); drop = uint8(0);}');
sfb.tr(ch, dg, wg, '[wif ~= 0]{n = uint16(1);}', 1, 2, 10);
sfb.tr(ch, dg, dr, sprintf('[n + 1 >= uint16(%s)]', ms), 2, 6, 12);
sfb.tr(ch, dr, wg, '[wif ~= 0]{n = uint16(1);}', 1, 1, 7);
sfb.tr(ch, wg, dg, '[wif == 0]{n = uint16(1);}', 1, 8, 4);
sfb.tr(ch, wg, we, sprintf('[n + 1 >= uint16(%s)]', ms), 2, 6, 12);
sfb.tr(ch, we, dg, '[wif == 0]{n = uint16(1);}', 1, 11, 5);
set_param(m, 'Description', 'Water-in-fuel debounce. Source of truth for firmware/gen/ecu_wifg.');
mb.finish(m);
end
