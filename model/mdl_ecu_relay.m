function mdl_ecu_relay(P)
%MDL_ECU_RELAY  Main relay, the board's own supply (mode.c relay_step).
%   OFF -> HELD with the ignition (pin 71 also closes it in hardware).
%   Ignition off: AFTER-RUN, asking for one save; the relay opens once
%   the engine has stopped and the save is written, or after
%   AFTERRUN_MAX_MS whatever happens.
m = 'ecu_relay';
mb.new(m);
ch = sfb.chart(m, 'MainRelay', {'ignition', 'uint8'; 'stopped', 'uint8'; 'written', 'uint8'}, ...
    {'relay', 'uint8'; 'afterrun', 'uint8'; 'save', 'uint8'});
sfb.local(ch, 'ms', 'uint16');
mx = sprintf('uint16(%s)', mb.num(P.AFTERRUN_MAX_MS));
g = sfb.state(ch, 'Relay\nentry: ms = uint16(0); save = uint8(0);\nduring: save = uint8(0);', [30 40 680 330]);
of = sfb.state(g, 'OFF\nentry: relay = uint8(0); afterrun = uint8(0);', [60 120 170 70]);
he = sfb.state(g, 'HELD\nentry: relay = uint8(1); afterrun = uint8(0);', [290 120 170 70]);
af = sfb.state(g, sprintf('AFTER_RUN\nentry: relay = uint8(1); afterrun = uint8(1);\nduring: ms = min(ms + 1, %s);', mx), [500 110 190 90]);
sfb.def(ch, g);
sfb.def(g, of);
sfb.tr(g, of, he, '[ignition ~= 0]', 1, 3, 9);
sfb.tr(g, he, af, '[ignition == 0]{save = uint8(1); ms = uint16(1);}', 1, 2, 10);
sfb.tr(g, af, he, '[ignition ~= 0]{ms = uint16(0);}', 1, 8, 4);
sfb.tr(g, af, of, sprintf('[(stopped ~= 0 && written ~= 0) || ms + 1 >= %s]', mx), 2, 7, 5);
set_param(m, 'Description', 'Main relay and after-run. Source of truth for firmware/gen/ecu_relay.');
mb.finish(m);
end
