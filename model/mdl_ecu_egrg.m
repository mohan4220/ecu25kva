function mdl_ecu_egrg(P)
%MDL_ECU_EGRG  EGR stall guard (mode.c egrg_step).
%   The time over EGR_STALL_A builds up and leaks away at the same rate.
%   NORMAL -> COAST at EGR_STALL_MS (raise once, the bridge coasts for
%   EGR_COOL_MS); the EGR_STALL_TRIES-th stall goes to LOCKED instead,
%   held to the next reset (an ignition cycle).
m = 'ecu_egrg';
mb.new(m);
ch = sfb.chart(m, 'EgrStallGuard', {'i_egr', 'single'}, {'off', 'uint8'; 'raise', 'uint8'});
sfb.local(ch, 'hot', 'uint16');
sfb.local(ch, 'cool', 'uint16');
sfb.local(ch, 'stalls', 'uint8');
a = mb.num(P.EGR_STALL_A); ms = mb.num(P.EGR_STALL_MS);
cool = mb.num(P.EGR_COOL_MS); tries = mb.num(P.EGR_STALL_TRIES);
g = sfb.state(ch, sprintf(['Guard\nentry: hot = uint16(0); cool = uint16(0); stalls = uint8(0); raise = uint8(0);\nduring: raise = uint8(0);\n' ...
    'if i_egr > single(%s)\n    hot = min(hot + 1, uint16(%s));\n' ...
    'elseif hot > 0\n    hot = hot - 1;\nend'], a, ms), [30 40 640 260]);
no = sfb.state(g, 'NORMAL\nentry: off = uint8(0);', [60 170 130 70]);
co = sfb.state(g, 'COAST\nentry: off = uint8(1);\nduring: cool = cool - 1;', [290 170 150 70]);
lo = sfb.state(g, 'LOCKED\nentry: off = uint8(1);', [510 170 130 70]);
sfb.def(ch, g);
sfb.def(g, no);
act = sprintf('hot = uint16(0); cool = uint16(%s); raise = uint8(1);', cool);
sfb.tr(g, no, lo, sprintf('[hot >= uint16(%s) && stalls + 1 >= uint8(%s)]{%s stalls = uint8(%s);}', ms, tries, act, tries), 1, 1, 11);
sfb.tr(g, no, co, sprintf('[hot >= uint16(%s)]{%s stalls = stalls + 1;}', ms, act), 2, 2, 10);
sfb.tr(g, co, no, '[cool <= 1]{cool = uint16(0);}', 1, 8, 4);
set_param(m, 'Description', 'EGR stall guard. Source of truth for firmware/gen/ecu_egrg.');
mb.finish(m);
end
