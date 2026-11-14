function mdl_ecu_boostm(P)
%MDL_ECU_BOOSTM  The boost rail's warnings (mode.c boostm_step), amber only.
%   Two parallel regions, each the water-in-fuel debounce:
%     HIGH: over BOOST_HIGH_V for BOOST_HIGH_MS -- the hardware zener
%           clamping at its low corner, below the BOOST_OV_V trip;
%     LOW:  under BOOST_LOW_V for BOOST_LOW_MS while cranking or running
%           (fuelling) -- a dead boost. 0 V means not measured.
%   Each raises once its condition has held, and drops once it has been
%   clear as long.
m = 'ecu_boostm';
mb.new(m);
ch = sfb.chart(m, 'BoostWarnings', {'v_rail', 'single'; 'fuelling', 'uint8'}, ...
    {'hi_raise', 'uint8'; 'hi_drop', 'uint8'; 'lo_raise', 'uint8'; 'lo_drop', 'uint8'});
ch.Decomposition = 'PARALLEL_AND';
sfb.local(ch, 'nh', 'uint16');
sfb.local(ch, 'nl', 'uint16');
hi = sfb.state(ch, 'HIGH', [30 30 700 300]);
hi.ExecutionOrder = 1;
lo = sfb.state(ch, 'LOW', [30 360 700 300]);
lo.ExecutionOrder = 2;
debounce(hi, sprintf('v_rail > single(%s)', mb.num(P.BOOST_HIGH_V)), P.BOOST_HIGH_MS, 'hi', 'nh');
debounce(lo, sprintf('fuelling ~= 0 && v_rail > single(0) && v_rail < single(%s)', mb.num(P.BOOST_LOW_V)), ...
    P.BOOST_LOW_MS, 'lo', 'nl');
set_param(m, 'Description', 'Boost rail warnings. Source of truth for firmware/gen/ecu_boostm.');
mb.finish(m);
end

function debounce(r, cond, ms, o, n)
% CLEARING -> CLEAR (drop) and SETTING -> SET (raise), each after ms ticks.
x = r.Position(1); y = r.Position(2);
lab = @(name, ra, dr, dur) sprintf('%s\nentry: %s_raise = uint8(%d); %s_drop = uint8(%d);%s', ...
    name, o, ra, o, dr, dur);
cnt = sprintf('\nduring: %s = %s + 1;', n, n);
cg = sfb.state(r, lab('CLEARING', 0, 0, cnt), [x+30 y+50 260 80]);
cl = sfb.state(r, lab('CLEAR', 0, 1, ''), [x+30 y+190 260 70]);
sg = sfb.state(r, lab('SETTING', 0, 0, cnt), [x+400 y+50 260 80]);
st = sfb.state(r, lab('SET', 1, 0, ''), [x+400 y+190 260 70]);
one = sprintf('{%s = uint16(1);}', n);
full = sprintf('[%s + 1 >= uint16(%s)]', n, mb.num(ms));
sfb.def(r, cg, sprintf('{%s = uint16(0); %s_raise = uint8(0); %s_drop = uint8(0);}', n, o, o));
sfb.tr(r, cg, sg, ['[' cond ']' one], 1, 2, 10);
sfb.tr(r, cg, cl, full, 2, 6, 12);
sfb.tr(r, cl, sg, ['[' cond ']' one], 1, 1, 7);
sfb.tr(r, sg, cg, ['[~(' cond ')]' one], 1, 8, 4);
sfb.tr(r, sg, st, full, 2, 6, 12);
sfb.tr(r, st, cg, ['[~(' cond ')]' one], 1, 11, 5);
end
