// The bundled firmware: firmware/core compiled and linked statically.
fn main() {
    let core = std::path::Path::new("../../../firmware/core");
    println!("cargo:rerun-if-changed={}", core.display());
    let mut files: Vec<_> = std::fs::read_dir(core)
        .unwrap()
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.extension().is_some_and(|x| x == "c"))
        .collect();
    files.sort();
    for f in &files {
        println!("cargo:rerun-if-changed={}", f.display());
    }
    cc::Build::new()
        .files(&files)
        .include(core)
        .flag_if_supported("-std=c99")
        .opt_level(2)
        .compile("ecucore");
}
