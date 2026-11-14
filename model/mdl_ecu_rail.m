function mdl_ecu_rail(P)
%MDL_ECU_RAIL  Rail pressure: PI on the metering-unit duty (firmware/core/rail.c).
%     err   = METER_NC ? set - rail : rail - set      (normally open: more duty, less flow)
%     integ = sat(integ_prev + (KI*err)*dt, 0, 1)
%     duty  = sat(integ + KP*err, 0, 1)
%   rst (rail_reset) zeroes the integral before the step.
m = 'ecu_rail';
mb.new(m);
S = 'single';
mb.in(m, 'set_bar', S); mb.in(m, 'rail_bar', S); mb.in(m, 'rst', 'uint8');
mb.out(m, 'duty', S);
if P.METER_NC
    mb.b(m, 'err', 'simulink/Math Operations/Sum', 'Inputs', '+-');
    mb.l(m, 'set_bar/1', 'err/1'); mb.l(m, 'rail_bar/1', 'err/2');
else
    mb.b(m, 'err', 'simulink/Math Operations/Sum', 'Inputs', '+-');
    mb.l(m, 'rail_bar/1', 'err/1'); mb.l(m, 'set_bar/1', 'err/2');
end
mb.k(m, 'ZERO', 0, S);
mb.b(m, 'integ_z', 'simulink/Discrete/Unit Delay', 'InitialCondition', '0');
mb.b(m, 'integ_prev', 'simulink/Signal Routing/Switch', 'Criteria', 'u2 ~= 0');
mb.l(m, 'ZERO/1', 'integ_prev/1'); mb.l(m, 'rst/1', 'integ_prev/2'); mb.l(m, 'integ_z/1', 'integ_prev/3');
mb.b(m, 'g_ki', 'simulink/Math Operations/Gain', 'Gain', mb.num(P.RAIL_KI));
mb.b(m, 'g_dt', 'simulink/Math Operations/Gain', 'Gain', mb.num(P.DT));
mb.b(m, 'integ_add', 'simulink/Math Operations/Sum', 'Inputs', '++');
mb.b(m, 'integ_sat', 'simulink/Discontinuities/Saturation', 'UpperLimit', '1', 'LowerLimit', '0');
mb.l(m, 'err/1', 'g_ki/1'); mb.l(m, 'g_ki/1', 'g_dt/1');
mb.l(m, 'integ_prev/1', 'integ_add/1'); mb.l(m, 'g_dt/1', 'integ_add/2');
mb.l(m, 'integ_add/1', 'integ_sat/1'); mb.l(m, 'integ_sat/1', 'integ_z/1');
mb.b(m, 'g_kp', 'simulink/Math Operations/Gain', 'Gain', mb.num(P.RAIL_KP));
mb.b(m, 'pi_add', 'simulink/Math Operations/Sum', 'Inputs', '++');
mb.b(m, 'duty_sat', 'simulink/Discontinuities/Saturation', 'UpperLimit', '1', 'LowerLimit', '0');
mb.l(m, 'err/1', 'g_kp/1');
mb.l(m, 'integ_sat/1', 'pi_add/1'); mb.l(m, 'g_kp/1', 'pi_add/2');
mb.l(m, 'pi_add/1', 'duty_sat/1'); mb.l(m, 'duty_sat/1', 'duty/1');
set_param(m, 'Description', 'Rail-pressure PI. Source of truth for firmware/gen/ecu_rail.');
mb.finish(m);
end
