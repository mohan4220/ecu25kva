function mdl_ecu_underg(P)
%MDL_ECU_UNDERG  Underspeed warning (mode.c underg_step). Amber only.
%   DISARMED until the start ramp is done (armed, worked out in ecu.c),
%   dropping the warning every tick. ARMED follows the speed band:
%   below UNDERSPEED_RPM for UNDERSPEED_MS -> LOW (raise); above
%   UNDERSPEED_CLEAR_RPM for UNDERSPEED_CLEAR_MS -> HIGH (drop); between
%   them nothing changes.
m = 'ecu_underg';
mb.new(m);
ch = sfb.chart(m, 'Underspeed', {'rpm', 'single'; 'armed', 'uint8'}, {'raise', 'uint8'; 'drop', 'uint8'});
sfb.local(ch, 'n', 'uint16');
lo = sprintf('single(%s)', mb.num(P.UNDERSPEED_RPM));
hi = sprintf('single(%s)', mb.num(P.UNDERSPEED_CLEAR_RPM));
nl = sprintf('uint16(%s)', mb.num(P.UNDERSPEED_MS));
nh = sprintf('uint16(%s)', mb.num(P.UNDERSPEED_CLEAR_MS));
dis = sfb.state(ch, 'DISARMED\nentry: raise = uint8(0); drop = uint8(1);', [40 40 180 70]);
arm = sfb.state(ch, 'ARMED', [40 170 760 300]);
mid = sfb.state(arm, 'MID\nentry: raise = uint8(0); drop = uint8(0);', [330 200 180 70]);
lc = sfb.state(arm, 'LOW_COUNT\nentry: raise = uint8(0); drop = uint8(0);\nduring: n = n + 1;', [70 250 200 80]);
lw = sfb.state(arm, 'LOW\nentry: raise = uint8(1); drop = uint8(0);', [70 380 200 70]);
hc = sfb.state(arm, 'HIGH_COUNT\nentry: raise = uint8(0); drop = uint8(0);\nduring: n = n + 1;', [570 250 200 80]);
hg = sfb.state(arm, 'HIGH\nentry: raise = uint8(0); drop = uint8(1);', [570 380 200 70]);
one = '{n = uint16(1);}';
sfb.def(ch, dis, '{n = uint16(0);}');
sfb.def(arm, mid);                 % never taken: arming enters a band directly
% arming goes straight to the band the speed is in, counting this tick
sfb.tr(ch, dis, lc, sprintf('[armed ~= 0 && rpm < %s]%s', lo, one), 1, 5, 0);
sfb.tr(ch, dis, hc, sprintf('[armed ~= 0 && rpm > %s]%s', hi, one), 2, 3, 0);
sfb.tr(ch, dis, mid, '[armed ~= 0]', 3, 4, 0);
sfb.tr(ch, arm, dis, '[armed == 0]', 1, 11, 7);
sfb.tr(arm, mid, lc, sprintf('[rpm < %s]%s', lo, one), 1, 8, 2);
sfb.tr(arm, mid, hc, sprintf('[rpm > %s]%s', hi, one), 2, 4, 10);
sfb.tr(arm, lc, hc, sprintf('[rpm > %s]%s', hi, one), 1, 4, 8);
sfb.tr(arm, lc, mid, sprintf('[rpm >= %s]', lo), 2, 2, 8);
sfb.tr(arm, lc, lw, sprintf('[n + 1 >= %s]', nl), 3, 6, 0);
sfb.tr(arm, lw, hc, sprintf('[rpm > %s]%s', hi, one), 1, 3, 7);
sfb.tr(arm, lw, mid, sprintf('[rpm >= %s]', lo), 2, 2, 7);
sfb.tr(arm, hc, lc, sprintf('[rpm < %s]%s', lo, one), 1, 8, 4);
sfb.tr(arm, hc, mid, sprintf('[rpm <= %s]', hi), 2, 10, 4);
sfb.tr(arm, hc, hg, sprintf('[n + 1 >= %s]', nh), 3, 6, 0);
sfb.tr(arm, hg, lc, sprintf('[rpm < %s]%s', lo, one), 1, 9, 5);
sfb.tr(arm, hg, mid, sprintf('[rpm <= %s]', hi), 2, 10, 5);
set_param(m, 'Description', 'Underspeed warning. Source of truth for firmware/gen/ecu_underg.');
mb.finish(m);
end
