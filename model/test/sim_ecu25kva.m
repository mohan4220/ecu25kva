function sim_ecu25kva()
%SIM_ECU25KVA  Run the whole ECU model, closed loop, and check it.
%   A start, 20 kW at 8 s, the stop switch at 16 s. The checks are the
%   firmware SIL scenarios' own limits (firmware/sim/run_sil.py), plus the
%   sensor chain, the injection the cylinder events compute, and the
%   J1939 frames the tasks send. Writes model/test/ecu25kva_sim.png.
here = fileparts(fileparts(mfilename('fullpath')));
addpath(here, fullfile(here, 'lib'));
load_system(fullfile(here, 'ecu25kva.slx'));
out = sim('ecu25kva');
g = @(n) out.get(n);
rpm = g('rpm'); mode = g('mode'); fuel = g('fuel_mg'); rail = g('rail_bar');
at = @(ts, t) double(ts.Data(find(ts.Time >= t, 1), :));
mean_in = @(ts, t0, t1) mean(double(ts.Data(ts.Time >= t0 & ts.Time < t1)));
fails = 0; n = 0;
    function check(what, ok, val)
        fprintf('%-58s %-10.4g %s\n', what, val, ternary(ok));
        fails = fails + ~ok; n = n + 1;
    end
    function s = ternary(ok), if ok, s = 'ok'; else, s = 'FAIL'; end, end
run_t = rpm.Time(find(mode.Data == 3, 1));
check('reaches RUN (s)', ~isempty(run_t) && run_t < 3, run_t);
check('speed at 7.5 s, 1500 +/- 15 rpm', abs(mean_in(rpm, 7.4, 7.5) - 1500) < 15, mean_in(rpm, 7.4, 7.5));
pk = max(double(rpm.Data(rpm.Time < 8)));
check('start overshoot under 1600 rpm', pk < 1600, pk);
lo = min(double(rpm.Data(rpm.Time >= 8 & rpm.Time < 16)));
check('lowest speed after 20 kW, over 1350 rpm', lo > 1350, lo);
check('speed 5 s after the load step', abs(mean_in(rpm, 12.9, 13) - 1500) < 15, mean_in(rpm, 12.9, 13));
check('rail tracks its setpoint at 13 s (bar)', abs(at(rail, 13) - at(g('set_bar'), 13)) < 50, at(rail, 13));
check('measured rail = true rail through the sensor (bar)', abs(at(rail, 13) - at(g('rail_true'), 13)) < 5, ...
      at(rail, 13) - at(g('rail_true'), 13));
check('coolant read through the NTC, 85 degC', abs(at(g('clt_c'), 13) - 85) < 1, at(g('clt_c'), 13));
check('stop switch: SHUTDOWN at 16 s', at(mode, 16.01) == 4, at(mode, 16.01));
check('fuel cut in SHUTDOWN (mg)', at(fuel, 16.01) == 0, at(fuel, 16.01));
check('engine coasting down: under 300 rpm by 20 s', at(rpm, 19.9) < 300, at(rpm, 19.9));
check('after-run not started: the ignition stays on', at(g('afterrun'), 19.9) == 0, at(g('afterrun'), 19.9));
check('boost stopped only in SHUTDOWN', at(g('boost_dis'), 12) == 0 && at(g('boost_dis'), 16.01) == 1, ...
      at(g('boost_dis'), 16.01));
dur = at(g('dur_us'), 13);
check('cylinder events: an injection computed under load (us)', dur > 400 && dur < 5000, dur);
e = at(g('eec1'), 13);
eec_rpm = (double(e(4)) + 256 * double(e(5))) * 0.125;
check('J1939 EEC1 carries the speed (rpm)', abs(eec_rpm - at(rpm, 12.98)) < 20, eec_rpm);
check('speed states: STEADY at 7.5 s', at(g('spd_state'), 7.5) == 3, at(g('spd_state'), 7.5));
check('speed states: OPERATING again after the 20 kW step', any(g('spd_state').Data(g('spd_state').Time > 8 & g('spd_state').Time < 9) == 2), 2);
check('EGR bridge coasts: no target yet (duty)', at(g('egr_duty'), 13) == 0, at(g('egr_duty'), 13));
check('metering current = duty x 13.5 V / 3.75 ohm, the measured coil (A)', abs(at(g('i_mu'), 13) - at(g('duty'), 13) * 13.5 / 3.75) < 0.02, at(g('i_mu'), 13));
t = at(g('et1_tx'), 13);
check('J1939 ET1 carries the coolant (degC)', abs(double(t(1)) - 40 - 85) <= 1, double(t(1)) - 40);
act = g('dg_act');
check('no diagnosis in a normal start, load and stop (faults seen)', ~any(act.Data(:)), nnz(any(act.Data, 1)));
check('no lamp lit in a normal run (ecu_lamps)', ~any(g('lamps').Data(:)), double(max(g('lamps').Data(:))));
check('metering coil at 13 s: the plant''s nominal 3.75 ohm, not drifted (ohm)', abs(at(g('mu_r'), 13) - 3.75) < 0.19, at(g('mu_r'), 13));
ic = at(g('ic1'), 13);
check('J1939 IC1 carries the charge air, 30 + 0.6 x 20 kW (degC)', abs(double(ic(3)) - 40 - 42) <= 1, double(ic(3)) - 40);
ef = at(g('eflp1_tx'), 13);
check('J1939 EFL/P1 byte 8: coolant level OK, 100 % (raw)', ef(8) == 250, double(ef(8)));

% ---- second run: the protection (decisions log 35). No stop switch.
% Battery 9.2 V from 4 s (running: 168/18 after 10 s); coolant level
% switch open from 5 s (111/18 after 5 s); coolant 85 degC until 9 s, then
% up 3.5 degC/s to 106 (110/16 2 s past 100 degC; 110/0 2 s past 104,
% Protect, and the DSE drops the ignition). Each fault's time is
% diag.c's, through the generated ecu_diag and ecu_deb.
in2 = Simulink.SimulationInput('ecu25kva');
in2 = in2.setModelParameter('StopTime', '25');
in2 = in2.setBlockParameter('ecu25kva/stop_sw', 'Time', '1e6');
in2 = in2.setBlockParameter('ecu25kva/v_bat', 'BreakpointsForDimension1', '[0 4 4.001 100]', ...
                             'ecu25kva/v_bat', 'Table', '[13.5 13.5 9.2 9.2]');
in2 = in2.setBlockParameter('ecu25kva/clt_low', 'Time', '5');
in2 = in2.setBlockParameter('ecu25kva/r_coil', 'Value', '4.5');   % not the nominal 3.75: it must be learned
in2 = in2.setBlockParameter('ecu25kva/clt_degc', 'BreakpointsForDimension1', '[0 9 15 100]', ...
                             'ecu25kva/clt_degc', 'Table', '[85 85 106 106]');
out2 = sim(in2);
g2 = @(n) out2.get(n);
act2 = g2('dg_act'); clt2 = g2('clt_c'); mode2 = g2('mode'); P = ecu_params();
first = @(k) act2.Time(find(act2.Data(:, k) ~= 0, 1));
over = @(c) clt2.Time(find(clt2.Data > c, 1));           % the ECU's own reading crosses c
t_lvl = first(14); t_low = first(11); t_warn = first(12); t_stop = first(13);
check('111/18 coolant level, 5 s after the switch opens (s)', abs(t_lvl - (5 + P.dg_deb(14) / 1000)) < 0.005, t_lvl);
check('168/18 battery low, 10 s after 9.2 V while running (s)', abs(t_low - (4 + P.dg_deb(11) / 1000)) < 0.005, t_low);
check(sprintf('110/16 coolant warning, %g s past %g degC read (s)', P.dg_deb(12) / 1000, P.DG_CLT_WARN_C), ...
      abs(t_warn - (over(P.DG_CLT_WARN_C) + P.dg_deb(12) / 1000)) < 0.005, t_warn);
check(sprintf('110/0 coolant stop, %g s past %g degC read (s)', P.dg_deb(13) / 1000, P.DG_CLT_STOP_C), ...
      abs(t_stop - (over(P.DG_CLT_STOP_C) + P.dg_deb(13) / 1000)) < 0.005, t_stop);
check('amber faults: still RUN just before the coolant stop', at(mode2, t_stop - 0.01) == 3, at(mode2, t_stop - 0.01));
check('Protect lit with the coolant stop', at(g2('protect'), t_stop) == 1, at(g2('protect'), t_stop));
t_shut = mode2.Time(find(mode2.Time >= t_stop & mode2.Data == 4, 1));
check('the DSE drops the ignition: SHUTDOWN within 5 ms of Protect (s)', ~isempty(t_shut) && t_shut - t_stop < 0.005, t_shut - t_stop);
check('a 4.5 ohm coil learned by 13 s, from the nominal 3.75 (ohm)', abs(at(g2('mu_r'), 13) - 4.5) < 0.225, at(g2('mu_r'), 13));
ef2 = at(g2('eflp1_tx'), 7);
check('J1939 EFL/P1 byte 8: the level switch open, 0 % (raw)', ef2(8) == 0, double(ef2(8)));
l2 = at(g2('lamps'), t_lvl + 0.01);
check('amber after the level fault, without Protect (lamps byte)', bitand(l2, P.LAMP_AMBER) ~= 0 && bitand(l2, P.LAMP_PROTECT) == 0, double(l2));
others = setdiff(1:14, [11 12 13 14]);
check('no other diagnosis in the protection run (faults seen)', ~any(any(act2.Data(:, others))), nnz(any(act2.Data(:, others), 1)));
f = figure('Visible', 'off', 'Position', [0 0 1000 800]);
subplot(4, 1, 1); plot(rpm.Time, rpm.Data); ylabel('rpm'); grid on;
title('ecu25kva: start, 20 kW at 8 s, stop switch at 16 s');
subplot(4, 1, 2); stairs(mode.Time, double(mode.Data)); ylabel('mode'); yticks(0:4);
yticklabels({'OFF', 'WAIT', 'CRANK', 'RUN', 'SHUTDOWN'}); grid on;
subplot(4, 1, 3); plot(fuel.Time, fuel.Data); ylabel('fuel, mg'); grid on;
subplot(4, 1, 4); plot(rail.Time, rail.Data, g('set_bar').Time, g('set_bar').Data, '--');
ylabel('rail, bar'); xlabel('s'); legend('rail (measured)', 'setpoint'); grid on;
exportgraphics(f, fullfile(here, 'test', 'ecu25kva_sim.png'));
close(f);
close_system('ecu25kva', 0);
if fails, error('sim_ecu25kva: %d of %d checks failed', fails, n); end
fprintf('sim_ecu25kva: all %d checks pass\n', n);
end
