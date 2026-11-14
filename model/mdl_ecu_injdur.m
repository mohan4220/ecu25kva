function mdl_ecu_injdur(P)
%MDL_ECU_INJDUR  Injector energising time (inject.c inject_dur_us):
%   t = fuel <= 0 ? 0 : (uint32)(DEAD + fuel / (K * sqrt(max(rail, RAIL_MIN))) + 0.5)
m = 'ecu_injdur';
mb.new(m);
S = 'single';
mb.in(m, 'fuel_mg', S); mb.in(m, 'rail_bar', S);
mb.out(m, 'dur_us', 'uint32');
mb.k(m, 'RAIL_MIN', P.INJ_RAIL_MIN, S);
mb.b(m, 'p', 'simulink/Math Operations/MinMax', 'Function', 'max', 'Inputs', '2');
mb.b(m, 'sqrt_p', 'simulink/Math Operations/Sqrt', 'OutDataTypeStr', S);
mb.b(m, 'g_k', 'simulink/Math Operations/Gain', 'Gain', mb.num(P.INJ_K));
mb.b(m, 'q', 'simulink/Math Operations/Product', 'Inputs', '*/');
mb.k(m, 'DEAD', P.INJ_DEAD_US, S);
mb.k(m, 'HALF', 0.5, S);
mb.b(m, 'add_dead', 'simulink/Math Operations/Sum', 'Inputs', '++');
mb.b(m, 'add_half', 'simulink/Math Operations/Sum', 'Inputs', '++');
mb.b(m, 'to_us', 'simulink/Signal Attributes/Data Type Conversion', ...
    'OutDataTypeStr', 'uint32', 'RndMeth', 'Zero', 'SaturateOnIntegerOverflow', 'off');
mb.k(m, 'ZERO', 0, S);
mb.b(m, 'on', 'simulink/Logic and Bit Operations/Relational Operator', 'Operator', '>');
mb.k(m, 'NONE', 0, 'uint32');
mb.b(m, 'dur', 'simulink/Signal Routing/Switch', 'Criteria', 'u2 ~= 0');
mb.l(m, 'rail_bar/1', 'p/1'); mb.l(m, 'RAIL_MIN/1', 'p/2');
mb.l(m, 'p/1', 'sqrt_p/1'); mb.l(m, 'sqrt_p/1', 'g_k/1');
mb.l(m, 'fuel_mg/1', 'q/1', 'on/1'); mb.l(m, 'g_k/1', 'q/2');
mb.l(m, 'DEAD/1', 'add_dead/1'); mb.l(m, 'q/1', 'add_dead/2');
mb.l(m, 'add_dead/1', 'add_half/1'); mb.l(m, 'HALF/1', 'add_half/2');
mb.l(m, 'add_half/1', 'to_us/1');
mb.l(m, 'ZERO/1', 'on/2');
mb.l(m, 'to_us/1', 'dur/1'); mb.l(m, 'on/1', 'dur/2'); mb.l(m, 'NONE/1', 'dur/3');
mb.l(m, 'dur/1', 'dur_us/1');
set_param(m, 'Description', 'Injector law, fitted to the old ECU (field evidence 2026-10-14 sec. 3d).');
mb.finish(m);
end
