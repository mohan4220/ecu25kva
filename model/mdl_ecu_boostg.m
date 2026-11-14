function mdl_ecu_boostg(P)
%MDL_ECU_BOOSTG  Boost-rail overvoltage guard (mode.c boostg_step).
%   OK -> HIGH while the rail is over BOOST_OV_V; HIGH -> LATCHED after
%   BOOST_OV_MS ticks, raising trip once. LATCHED holds to the next reset
%   (an ignition cycle). dis = latched or shut down.
m = 'ecu_boostg';
mb.new(m);
ch = sfb.chart(m, 'BoostGuard', {'v_rail', 'single'; 'shut', 'uint8'}, ...
    {'dis', 'uint8'; 'trip', 'uint8'});
sfb.local(ch, 'cnt', 'uint16');
sfb.local(ch, 'latched', 'uint8');
th = mb.num(P.BOOST_OV_V); n = mb.num(P.BOOST_OV_MS);
g = sfb.state(ch, 'Guard\nentry: cnt = uint16(0); latched = uint8(0); dis = uint8(0); trip = uint8(0);\nduring: trip = uint8(0); dis = uint8(shut ~= 0 || latched ~= 0);', [30 40 600 230]);
ok = sfb.state(g, 'OK', [60 120 110 70]);
hi = sfb.state(g, 'HIGH\nduring: cnt = cnt + 1;', [250 120 140 70]);
la = sfb.state(g, 'LATCHED\nentry: latched = uint8(1); dis = uint8(1);', [460 120 150 70]);
sfb.def(ch, g);
sfb.def(g, ok);
sfb.tr(g, ok, hi, sprintf('[v_rail > single(%s)]{cnt = uint16(1);}', th), 1, 2, 10);
sfb.tr(g, hi, ok, sprintf('[v_rail <= single(%s)]', th), 1, 8, 4);
sfb.tr(g, hi, la, sprintf('[cnt + 1 >= uint16(%s)]{trip = uint8(1);}', n), 2, 3, 9);
set_param(m, 'Description', 'Boost overvoltage guard. Source of truth for firmware/gen/ecu_boostg.');
mb.finish(m);
end
