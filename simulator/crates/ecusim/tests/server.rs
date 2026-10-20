//! The HTTP side, over plain TCP.
use ecusim::{live, server};
use sim::Firmware;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::{mpsc, Arc, Mutex};
use std::time::{Duration, Instant};

static ONE: Mutex<()> = Mutex::new(()); // tests that run a Sim share the bundled firmware

struct Srv {
    port: u16,
    tx: mpsc::Sender<live::Cmd>,
    hub: Arc<live::Hub>,
}

impl Drop for Srv {
    fn drop(&mut self) {
        let _ = self.tx.send(live::Cmd::Reset); // frees the firmware
    }
}

fn start(share: bool) -> Srv {
    let free = TcpListener::bind("127.0.0.1:0").unwrap().local_addr().unwrap().port();
    let (srv, port) = server::bind(free, share).unwrap();
    let dir = std::env::temp_dir().join(format!("ecusim-srv-{}-{port}", std::process::id()));
    let (tx, hub) = live::spawn(Firmware::bundled(), dir.clone());
    let (tx2, hub2) = (tx.clone(), hub.clone());
    std::thread::spawn(move || server::serve(srv, tx2, hub2, share, dir));
    Srv { port, tx, hub }
}

/// (status, body)
fn http(port: u16, method: &str, path: &str, body: &[u8]) -> (u16, Vec<u8>) {
    let mut s = TcpStream::connect(("127.0.0.1", port)).unwrap();
    write!(s, "{method} {path} HTTP/1.1\r\nHost: x\r\nContent-Length: {}\r\nConnection: close\r\n\r\n", body.len()).unwrap();
    s.write_all(body).unwrap();
    let mut r = vec![];
    s.read_to_end(&mut r).unwrap();
    let split = r.windows(4).position(|w| w == b"\r\n\r\n").unwrap();
    let head = String::from_utf8_lossy(&r[..split]).to_string();
    let code = head.split(' ').nth(1).unwrap().parse().unwrap();
    (code, r[split + 4..].to_vec())
}

fn text(b: &[u8]) -> String {
    String::from_utf8_lossy(b).into_owned()
}

#[test]
fn port_busy_takes_next() {
    let held = TcpListener::bind("127.0.0.1:0").unwrap();
    let p = held.local_addr().unwrap().port();
    let (_srv, got) = server::bind(p, false).unwrap();
    assert!(got > p && got <= p + 20, "{p} -> {got}");
}

#[test]
fn serves_the_page() {
    let s = start(false);
    let (code, body) = http(s.port, "GET", "/", b"");
    assert_eq!(code, 200);
    assert!(text(&body).contains("<title>"));
    assert_eq!(http(s.port, "GET", "/uPlot.iife.min.js", b"").0, 200);
    assert_eq!(http(s.port, "GET", "/nope", b"").0, 404);
}

#[test]
fn cmd_load_applies() {
    let _one = ONE.lock().unwrap_or_else(|e| e.into_inner());
    let s = start(false);
    let rx = s.hub.subscribe();
    assert_eq!(http(s.port, "POST", "/cmd", b"start").0, 200);
    assert_eq!(http(s.port, "POST", "/cmd", b"load 20").0, 200);
    let end = Instant::now() + Duration::from_secs(10);
    loop {
        assert!(Instant::now() < end, "no load event");
        if let Ok(b) = rx.recv_timeout(Duration::from_millis(200)) {
            if b.starts_with("event: event") && b.contains(" load 20") {
                break;
            }
        }
    }
    assert_eq!(http(s.port, "POST", "/cmd", b"speed max").0, 200);
    assert_eq!(http(s.port, "POST", "/cmd", b"load").0, 400);
}

#[test]
fn scenario_errors_have_lines() {
    let s = start(false);
    let (code, body) = http(s.port, "POST", "/scenario?name=bad", b"0 start\r\n1 fly\r\n");
    assert_eq!(code, 400);
    let v: serde_json::Value = serde_json::from_slice(&body).unwrap();
    assert_eq!(v[0]["line"], 2);
    assert!(v[1]["msg"].as_str().unwrap().contains("end"));
}

#[test]
fn firmware_refused_under_share() {
    let s = start(true);
    assert_eq!(http(s.port, "POST", "/firmware?name=x.dylib", b"abc").0, 403);
}

#[test]
fn firmware_garbage_400() {
    let s = start(false);
    let (code, body) = http(s.port, "POST", "/firmware?name=x.dll", &[0x5Au8; 512]);
    assert_eq!(code, 400, "{}", text(&body));
    assert!(!body.is_empty());
}

#[test]
fn library_lists_sil() {
    let s = start(false);
    let (code, body) = http(s.port, "GET", "/library", b"");
    assert_eq!(code, 200);
    let v: serde_json::Value = serde_json::from_slice(&body).unwrap();
    let sil = v.as_array().unwrap().iter().filter(|e| e["name"].as_str().unwrap().starts_with("sil/")).count();
    assert_eq!(sil, 16);
    let (code, body) = http(s.port, "GET", "/library/sil/01-start.seq", b"");
    assert_eq!(code, 200);
    assert!(text(&body).contains("0 start"));
    assert_eq!(http(s.port, "GET", "/library/../Cargo.toml", b"").0, 404);
    assert_eq!(http(s.port, "GET", "/runs/..%2F..%2Fsecret/trace.csv", b"").0, 404);
}

#[test]
fn sse_subscriber_dropped_on_disconnect() {
    let _one = ONE.lock().unwrap_or_else(|e| e.into_inner());
    let s = start(false);
    assert_eq!(http(s.port, "POST", "/cmd", b"start").0, 200);
    let mut c = TcpStream::connect(("127.0.0.1", s.port)).unwrap();
    write!(c, "GET /events HTTP/1.1\r\nHost: x\r\n\r\n").unwrap();
    let mut got = vec![0u8; 4096];
    let n = c.read(&mut got).unwrap();
    assert!(text(&got[..n]).contains("text/event-stream"));
    let end = Instant::now() + Duration::from_secs(5);
    while s.hub.count() == 0 {
        assert!(Instant::now() < end);
        std::thread::sleep(Duration::from_millis(10));
    }
    drop(c);
    let end = Instant::now() + Duration::from_secs(5);
    while s.hub.count() > 0 {
        assert!(Instant::now() < end, "dead subscriber kept");
        std::thread::sleep(Duration::from_millis(20));
    }
    // still running, and a new tab gets the stream
    let mut c = TcpStream::connect(("127.0.0.1", s.port)).unwrap();
    write!(c, "GET /events HTTP/1.1\r\nHost: x\r\n\r\n").unwrap();
    c.set_read_timeout(Some(Duration::from_secs(5))).unwrap();
    let mut seen = String::new();
    while !seen.contains("\"mode\":\"running\"") {
        let n = c.read(&mut got).unwrap();
        assert!(n > 0);
        seen += &text(&got[..n]);
    }
}
