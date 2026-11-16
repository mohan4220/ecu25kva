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
t = at(g('et1_tx'), 13);
check('J1939 ET1 carries the coolant (degC)', abs(double(t(1)) - 40 - 85) <= 1, double(t(1)) - 40);
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
