//! HTTP and Server-Sent Events (spec section 6): the embedded page, the
//! event stream, commands, scripts, firmware, the library and run folders.
use crate::library::LIBRARY;
use crate::live::{Cmd, Hub};
use serde_json::json;
use sim::{seq, Firmware};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::sync::{mpsc, Arc};
use tiny_http::{Header, Method, Request, Response, Server};

const FILES: &[(&str, &str, &[u8])] = &[
    ("/", "text/html; charset=utf-8", include_bytes!("../ui/index.html")),
    ("/app.js", "text/javascript; charset=utf-8", include_bytes!("../ui/app.js")),
    ("/app.css", "text/css; charset=utf-8", include_bytes!("../ui/app.css")),
    ("/uPlot.iife.min.js", "text/javascript; charset=utf-8", include_bytes!("../ui/uPlot.iife.min.js")),
    ("/uPlot.min.css", "text/css; charset=utf-8", include_bytes!("../ui/uPlot.min.css")),
];
const RUN_FILES: [&str; 5] = ["trace.csv", "can.csv", "events.txt", "report.txt", "firmware.txt"];
const MAX_BODY: usize = 64 << 20;

/// Binds `port`, or the next free one of the 20 after it. Local only,
/// unless `share`.
pub fn bind(port: u16, share: bool) -> Result<(Server, u16), String> {
    let host = if share { "0.0.0.0" } else { "127.0.0.1" };
    for p in port..=port.saturating_add(20) {
        if let Ok(s) = Server::http((host, p)) {
            return Ok((s, p));
        }
    }
    Err(format!("no free port in {port}..{}", port.saturating_add(20)))
}

/// One thread per request; never returns.
pub fn serve(server: Server, tx: mpsc::Sender<Cmd>, hub: Arc<Hub>, share: bool, runs_dir: PathBuf) {
    let port = server.server_addr().to_ip().map_or(0, |a| a.port());
    for req in server.incoming_requests() {
        let (tx, hub, runs_dir) = (tx.clone(), hub.clone(), runs_dir.clone());
        std::thread::spawn(move || {
            if trusted(&req, port, share) {
                handle(req, &tx, &hub, share, &runs_dir)
            } else {
                text(req, 403, "refused: this request did not come from the simulator's own page")
            }
        });
    }
}

/// Only the simulator's own page may talk to it. Any web site the user
/// visits can send a POST to 127.0.0.1 (no preflight for a plain body), and
/// /firmware loads native code; a DNS-rebinding name can pose as us. So:
/// the Host must be ours (locally), and an Origin, if sent, must match it.
fn trusted(req: &Request, port: u16, share: bool) -> bool {
    let get = |name: &'static str| {
        req.headers().iter().find(|h| h.field.equiv(name)).map(|h| h.value.as_str().to_string())
    };
    let host = get("Host").unwrap_or_default();
    if !share && host != format!("127.0.0.1:{port}") && host != format!("localhost:{port}") {
        return false;
    }
    get("Origin").is_none_or(|o| o == format!("http://{host}"))
}

fn header(k: &str, v: &str) -> Header {
    Header::from_bytes(k, v).unwrap()
}

fn reply(req: Request, code: u16, kind: &str, body: impl Into<Vec<u8>>) {
    let _ = req.respond(Response::from_data(body.into()).with_status_code(code).with_header(header("Content-Type", kind)));
}

fn text(req: Request, code: u16, body: &str) {
    reply(req, code, "text/plain; charset=utf-8", body);
}

fn json_reply(req: Request, code: u16, v: serde_json::Value) {
    reply(req, code, "application/json", v.to_string());
}

/// A single path component a user may name: no separators, no parent, no escapes.
fn plain(s: &str) -> bool {
    !s.is_empty() && !s.contains(['/', '\\', '%']) && s != "." && s != ".."
}

fn query<'a>(url: &'a str, key: &str) -> Option<&'a str> {
    url.split_once('?')?.1.split('&').find_map(|kv| kv.strip_prefix(key)?.strip_prefix('='))
}

fn handle(mut req: Request, tx: &mpsc::Sender<Cmd>, hub: &Hub, share: bool, runs_dir: &Path) {
    let url = req.url().to_string();
    let path = url.split('?').next().unwrap_or("").to_string();
    let mut body = vec![];
    if *req.method() == Method::Post {
        if req.as_reader().take(MAX_BODY as u64 + 1).read_to_end(&mut body).is_err() || body.len() > MAX_BODY {
            return text(req, 413, "too large");
        }
    }
    match (req.method().clone(), path.as_str()) {
        (Method::Get, "/events") => events(req, hub),
        (Method::Get, p) if FILES.iter().any(|f| f.0 == p) => {
            let f = FILES.iter().find(|f| f.0 == p).unwrap();
            reply(req, 200, f.1, f.2)
        }
        (Method::Post, "/cmd") => {
            let line = String::from_utf8_lossy(&body).trim().to_string();
            let cmd = match line.as_str() {
                "run" => Cmd::Run,
                "pause" => Cmd::Pause,
                "stop" => Cmd::Stop,
                "reset" => Cmd::Reset,
                "speed max" => Cmd::Speed(None),
                l if l.starts_with("speed ") => match l[6..].trim().parse::<f64>() {
                    Ok(x) if x > 0.0 => Cmd::Speed(Some(x)),
                    _ => return text(req, 400, "speed is a number above 0, or max"),
                },
                l => match seq::parse_action(l) {
                    Ok(_) => Cmd::Line(l.to_string()),
                    Err(e) => return text(req, 400, &e),
                },
            };
            let _ = tx.send(cmd);
            text(req, 200, "ok")
        }
        (Method::Post, "/scenario") => {
            let name = query(&url, "name").filter(|n| plain(n)).unwrap_or("scenario").to_string();
            match seq::parse(&name, &String::from_utf8_lossy(&body)) {
                Ok(s) => {
                    let _ = tx.send(Cmd::Script(s));
                    json_reply(req, 200, json!("ok"))
                }
                Err(errs) => json_reply(req, 400,
                    json!(errs.iter().map(|(l, m)| json!({"line": l, "msg": m})).collect::<Vec<_>>())),
            }
        }
        (Method::Post, "/firmware") => {
            if share {
                return text(req, 403, "firmware cannot be loaded in --share mode");
            }
            let name = query(&url, "name").filter(|n| plain(n)).unwrap_or("firmware.lib");
            let dir = std::env::temp_dir().join(format!("ecusim-upload-{}-{}", std::process::id(),
                std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()));
            let file = dir.join(name);
            let loaded = std::fs::create_dir_all(&dir).and_then(|_| std::fs::write(&file, &body))
                .map_err(|e| e.to_string())
                .and_then(|_| Firmware::load(&file));
            let _ = std::fs::remove_dir_all(&dir); // Firmware::load keeps its own copy
            match loaded {
                Ok(fw) => {
                    let v = json!({"name": fw.name, "abi": fw.abi, "sha256": fw.sha256});
                    let _ = tx.send(Cmd::Firmware(fw));
                    json_reply(req, 200, v)
                }
                Err(e) => text(req, 400, &e),
            }
        }
        (Method::Get, "/library") => {
            let mut v: Vec<_> = LIBRARY.iter().map(|(n, _)| json!({"name": n, "source": "bundled"})).collect();
            for n in local_scenarios() {
                v.push(json!({"name": format!("local/{n}"), "source": "local"}));
            }
            json_reply(req, 200, json!(v))
        }
        (Method::Get, p) if p.starts_with("/library/") => {
            let name = &p["/library/".len()..];
            if let Some((_, t)) = LIBRARY.iter().find(|(n, _)| *n == name) {
                return text(req, 200, t);
            }
            match name.strip_prefix("local/").filter(|n| plain(n) && n.ends_with(".seq"))
                .and_then(|n| std::fs::read_to_string(Path::new("scenarios").join(n)).ok()) {
                Some(t) => text(req, 200, &t),
                None => text(req, 404, "no such scenario"),
            }
        }
        (Method::Get, "/runs") => {
            let mut v: Vec<String> = std::fs::read_dir(runs_dir).into_iter().flatten().flatten()
                .filter(|e| e.path().is_dir())
                .filter_map(|e| e.file_name().into_string().ok())
                .collect();
            v.sort_unstable_by(|a, b| b.cmp(a));
            json_reply(req, 200, json!(v))
        }
        (Method::Get, p) if p.starts_with("/runs/") => {
            let rest = &p["/runs/".len()..];
            let ok = rest.split_once('/').filter(|(id, f)| plain(id) && RUN_FILES.contains(f));
            match ok.and_then(|(id, f)| std::fs::read(runs_dir.join(id).join(f)).ok()) {
                Some(b) => reply(req, 200, "text/plain; charset=utf-8", b),
                None => text(req, 404, "no such run file"),
            }
        }
        _ => text(req, 404, "not found"),
    }
}

/// `.seq` files in ./scenarios, beside where ecusim was started.
fn local_scenarios() -> Vec<String> {
    let mut v: Vec<String> = std::fs::read_dir("scenarios").into_iter().flatten().flatten()
        .filter_map(|e| e.file_name().into_string().ok())
        .filter(|n| n.ends_with(".seq"))
        .collect();
    v.sort();
    v
}

/// The event stream, written straight to the socket so each block goes out
/// at once. A write that fails (the tab closed) ends it; dropping the
/// receiver makes the hub forget this subscriber.
fn events(req: Request, hub: &Hub) {
    let rx = hub.subscribe();
    let mut w = req.into_writer();
    let head = "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nCache-Control: no-cache\r\nConnection: keep-alive\r\n\r\n";
    if w.write_all(head.as_bytes()).and_then(|_| w.flush()).is_err() {
        return;
    }
    while let Ok(block) = rx.recv() {
        if w.write_all(block.as_bytes()).and_then(|_| w.flush()).is_err() {
            return;
        }
    }
}
