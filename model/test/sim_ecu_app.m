function sim_ecu_app()
%SIM_ECU_APP  Run the closed-loop application model and check it.
%   A start, 20 kW at 8 s, the stop switch at 16 s. The checks are the
%   firmware SIL scenarios' own limits (firmware/sim/run_sil.py).
%   Writes model/test/ecu_app_sim.png.
here = fileparts(fileparts(mfilename('fullpath')));
addpath(here, fullfile(here, 'lib'));
load_system(fullfile(here, 'ecu_app.slx'));
out = sim('ecu_app');
g = @(n) out.get(n);
rpm = g('rpm'); mode = g('mode'); fuel = g('fuel_mg'); rail = g('rail_bar');
at = @(ts, t) double(ts.Data(find(ts.Time >= t, 1)));
mean_in = @(ts, t0, t1) mean(double(ts.Data(ts.Time >= t0 & ts.Time < t1)));
fails = 0;
    function check(what, ok, val)
        fprintf('%-52s %-10.4g %s\n', what, val, ternary(ok));
        fails = fails + ~ok;
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
check('stop switch: SHUTDOWN at 16 s', at(mode, 16.01) == 4, at(mode, 16.01));
check('fuel cut in SHUTDOWN (mg)', at(fuel, 16.01) == 0, at(fuel, 16.01));
check('engine coasting down: under 300 rpm by 20 s', at(rpm, 19.9) < 300, at(rpm, 19.9));
check('after-run not started: the ignition stays on', at(g('afterrun'), 19.9) == 0, at(g('afterrun'), 19.9));
check('boost not stopped: rail at 99.7 V, below the trip', at(g('boost_dis'), 12) == 0 && at(g('boost_dis'), 16.01) == 1, at(g('boost_dis'), 16.01));
f = figure('Visible', 'off', 'Position', [0 0 1000 800]);
subplot(4, 1, 1); plot(rpm.Time, rpm.Data); ylabel('rpm'); grid on; title('ecu\_app: start, 20 kW at 8 s, stop switch at 16 s');
subplot(4, 1, 2); stairs(mode.Time, double(mode.Data)); ylabel('mode'); yticks(0:4); yticklabels({'OFF', 'WAIT', 'CRANK', 'RUN', 'SHUTDOWN'}); grid on;
subplot(4, 1, 3); plot(fuel.Time, fuel.Data); ylabel('fuel, mg'); grid on;
subplot(4, 1, 4); plot(rail.Time, rail.Data, g('set_bar').Time, g('set_bar').Data, '--'); ylabel('rail, bar'); xlabel('s'); legend('rail', 'setpoint'); grid on;
exportgraphics(f, fullfile(here, 'test', 'ecu_app_sim.png'));
close_system('ecu_app', 0);
if fails, error('sim_ecu_app: %d check(s) failed', fails); end
fprintf('sim_ecu_app: all checks pass\n');
end
