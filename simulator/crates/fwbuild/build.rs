fn main() {
    println!("cargo:rustc-env=FWBUILD_TARGET={}", std::env::var("TARGET").unwrap());
}
