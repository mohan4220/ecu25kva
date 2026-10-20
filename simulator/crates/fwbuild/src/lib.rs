//! Builds firmware/core as the platform's dynamic library, with the C
//! compiler `cc` finds (MSVC on Windows, clang on macOS, gcc on Linux),
//! for ecusim's "Load firmware".
use std::path::{Path, PathBuf};

const TARGET: &str = env!("FWBUILD_TARGET");

pub fn lib_name() -> &'static str {
    if cfg!(windows) {
        "ecu_fw.dll"
    } else if cfg!(target_os = "macos") {
        "ecu_fw.dylib"
    } else {
        "ecu_fw.so"
    }
}

/// The repository's firmware/core.
pub fn default_core() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../firmware/core")
}

/// Compiles every *.c in `core` into one shared library at `out`.
/// `defines` are NAME or NAME=VALUE.
pub fn build(core: &Path, out: &Path, defines: &[&str]) -> Result<(), String> {
    let mut files: Vec<PathBuf> = std::fs::read_dir(core)
        .map_err(|e| format!("{}: {e}", core.display()))?
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.extension().is_some_and(|x| x == "c"))
        .collect();
    files.sort();
    if files.is_empty() {
        return Err(format!("no .c files in {}", core.display()));
    }
    if let Some(dir) = out.parent() {
        std::fs::create_dir_all(dir).map_err(|e| e.to_string())?;
    }
    let tool = cc::Build::new()
        .target(TARGET)
        .host(TARGET)
        .opt_level(2)
        .debug(false)
        .cargo_metadata(false)
        .cargo_warnings(false)
        .try_get_compiler()
        .map_err(|e| format!("no C compiler: {e}"))?;
    let mut cmd = tool.to_command();
    if tool.is_like_msvc() {
        let obj = std::env::temp_dir().join(format!("fwbuild-{}", std::process::id()));
        std::fs::create_dir_all(&obj).map_err(|e| e.to_string())?;
        cmd.args(["/nologo", "/O2", "/LD", "/DECU_DLL"]);
        cmd.args(defines.iter().map(|d| format!("/D{d}")));
        cmd.args(&files);
        cmd.arg(format!("/Fe:{}", out.display()));
        cmd.arg(format!("/Fo:{}\\", obj.display()));
    } else {
        cmd.args(["-std=c99", "-O2", "-shared", "-fPIC"]);
        cmd.args(defines.iter().map(|d| format!("-D{d}")));
        cmd.args(&files);
        cmd.arg("-o").arg(out).arg("-lm");
    }
    let r = cmd.output().map_err(|e| format!("running the C compiler: {e}"))?;
    if !r.status.success() {
        return Err(format!("{}{}", String::from_utf8_lossy(&r.stdout), String::from_utf8_lossy(&r.stderr)));
    }
    Ok(())
}
