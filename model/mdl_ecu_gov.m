function mdl_ecu_gov(P)
%MDL_ECU_GOV  Speed governor: PI on rpm error, output fuel per injection (mg).
%   Same arithmetic as firmware/core/govern.c, step for step:
%     set   = sat(set_prev + RAMP*dt, 0, SET)        setpoint ramp from RUN entry
%     tgt   = droop ? SET*(1 - DROOP*fuel_prev/RATED) : SET
%     err   = min(set, tgt) - rpm
%     integ = sat(integ_prev + (KI*err)*dt, 0, FUEL_MAX)
%     fuel  = sat(integ + KP*err, 0, FUEL_MAX)
%   gov_reset is the rst input: on that step the previous values are
%   replaced by fuel0 / min(rpm0, SET), then the step runs as usual --
%   which is what C does when gov_reset is followed by gov_step.
m = 'ecu_gov';
mb.new(m);
S = 'single';
mb.in(m, 'rpm', S); mb.in(m, 'droop', 'uint8'); mb.in(m, 'rst', 'uint8');
mb.in(m, 'fuel0', S); mb.in(m, 'rpm0', S);
mb.out(m, 'fuel', S); mb.out(m, 'set', S);

% --- setpoint ramp
mb.k(m, 'SET', P.GOV_RPM_SET, S);
mb.b(m, 'set_init', 'simulink/Math Operations/MinMax', 'Function', 'min', 'Inputs', '2');
mb.b(m, 'set_z', 'simulink/Discrete/Unit Delay', 'InitialCondition', '0');
mb.b(m, 'set_prev', 'simulink/Signal Routing/Switch', 'Criteria', 'u2 ~= 0');
mb.k(m, 'RAMP_DT', single(P.GOV_RAMP_RPM_S) * single(P.DT), S);
mb.b(m, 'set_add', 'simulink/Math Operations/Sum', 'Inputs', '++');
mb.b(m, 'set_sat', 'simulink/Discontinuities/Saturation', 'UpperLimit', mb.num(P.GOV_RPM_SET), 'LowerLimit', '0');
mb.l(m, 'rpm0/1', 'set_init/1'); mb.l(m, 'SET/1', 'set_init/2');
mb.l(m, 'set_init/1', 'set_prev/1'); mb.l(m, 'rst/1', 'set_prev/2'); mb.l(m, 'set_z/1', 'set_prev/3');
mb.l(m, 'set_prev/1', 'set_add/1'); mb.l(m, 'RAMP_DT/1', 'set_add/2');
mb.l(m, 'set_add/1', 'set_sat/1');
mb.l(m, 'set_sat/1', 'set_z/1', 'set/1');

% --- droop target, from the previous step's fuel
mb.b(m, 'fuel_z', 'simulink/Discrete/Unit Delay', 'InitialCondition', '0');
mb.b(m, 'fuel_prev', 'simulink/Signal Routing/Switch', 'Criteria', 'u2 ~= 0');
mb.l(m, 'fuel0/1', 'fuel_prev/1'); mb.l(m, 'rst/1', 'fuel_prev/2'); mb.l(m, 'fuel_z/1', 'fuel_prev/3');
mb.b(m, 'g_droop', 'simulink/Math Operations/Gain', 'Gain', mb.num(P.GOV_DROOP));
mb.k(m, 'RATED', P.FUEL_RATED_MG, S);
mb.b(m, 'div_rated', 'simulink/Math Operations/Product', 'Inputs', '*/');
mb.k(m, 'ONE', 1, S);
mb.b(m, 'one_minus', 'simulink/Math Operations/Sum', 'Inputs', '+-');
mb.b(m, 'g_set', 'simulink/Math Operations/Gain', 'Gain', mb.num(P.GOV_RPM_SET));
mb.b(m, 'tgt', 'simulink/Signal Routing/Switch', 'Criteria', 'u2 ~= 0');
mb.l(m, 'fuel_prev/1', 'g_droop/1');
mb.l(m, 'g_droop/1', 'div_rated/1'); mb.l(m, 'RATED/1', 'div_rated/2');
mb.l(m, 'ONE/1', 'one_minus/1'); mb.l(m, 'div_rated/1', 'one_minus/2');
mb.l(m, 'one_minus/1', 'g_set/1');
mb.l(m, 'g_set/1', 'tgt/1'); mb.l(m, 'droop/1', 'tgt/2'); mb.l(m, 'SET/1', 'tgt/3');

% --- error
mb.b(m, 'sp', 'simulink/Math Operations/MinMax', 'Function', 'min', 'Inputs', '2');
mb.b(m, 'err', 'simulink/Math Operations/Sum', 'Inputs', '+-');
mb.l(m, 'set_sat/1', 'sp/1'); mb.l(m, 'tgt/1', 'sp/2');
mb.l(m, 'sp/1', 'err/1'); mb.l(m, 'rpm/1', 'err/2');

% --- integral, clamped (anti-windup)
mb.b(m, 'integ_z', 'simulink/Discrete/Unit Delay', 'InitialCondition', '0');
mb.b(m, 'integ_prev', 'simulink/Signal Routing/Switch', 'Criteria', 'u2 ~= 0');
mb.b(m, 'g_ki', 'simulink/Math Operations/Gain', 'Gain', mb.num(P.GOV_KI));
mb.b(m, 'g_dt', 'simulink/Math Operations/Gain', 'Gain', mb.num(P.DT));
mb.b(m, 'integ_add', 'simulink/Math Operations/Sum', 'Inputs', '++');
mb.b(m, 'integ_sat', 'simulink/Discontinuities/Saturation', 'UpperLimit', mb.num(P.FUEL_MAX_MG), 'LowerLimit', '0');
mb.l(m, 'fuel0/1', 'integ_prev/1'); mb.l(m, 'rst/1', 'integ_prev/2'); mb.l(m, 'integ_z/1', 'integ_prev/3');
mb.l(m, 'err/1', 'g_ki/1'); mb.l(m, 'g_ki/1', 'g_dt/1');
mb.l(m, 'integ_prev/1', 'integ_add/1'); mb.l(m, 'g_dt/1', 'integ_add/2');
mb.l(m, 'integ_add/1', 'integ_sat/1'); mb.l(m, 'integ_sat/1', 'integ_z/1');

% --- proportional, output clamped
mb.b(m, 'g_kp', 'simulink/Math Operations/Gain', 'Gain', mb.num(P.GOV_KP));
mb.b(m, 'pi_add', 'simulink/Math Operations/Sum', 'Inputs', '++');
mb.b(m, 'fuel_sat', 'simulink/Discontinuities/Saturation', 'UpperLimit', mb.num(P.FUEL_MAX_MG), 'LowerLimit', '0');
mb.l(m, 'err/1', 'g_kp/1');
mb.l(m, 'integ_sat/1', 'pi_add/1'); mb.l(m, 'g_kp/1', 'pi_add/2');
mb.l(m, 'pi_add/1', 'fuel_sat/1');
mb.l(m, 'fuel_sat/1', 'fuel_z/1', 'fuel/1');

set_param(m, 'Description', 'Speed governor. Source of truth for firmware/gen/gov; see model/README.md.');
mb.finish(m);
end
