fn main() {
    tonic_build::configure()
        .build_server(true)
        .build_client(false)
        .compile(&["../../proto/atr_transport.proto"], &["../../proto"])
        .expect("compile proto");
}
