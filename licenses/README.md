# Binary runtime notices

The application is MIT-licensed; see [LICENSE](../LICENSE). Binary archives also include these
third-party notices, whose separate terms remain in effect:

- `THIRD_PARTY_NOTICES.txt`: license texts from the locked target's normal/build Cargo graph.
- `rust/COPYRIGHT-library.html` and `rust/licenses/`: the pinned compiler distribution's standard
  library inventory and license texts, copied verbatim. This conservative inventory can cover
  components or platforms not used by this executable; it does not change the application's license.
- Linux only, `musl-1.2.5.COPYRIGHT`: the complete musl runtime copyright inventory.

Rust documents its generated inventory in its
[copyright record](https://github.com/rust-lang/rust/blob/1.99.1/COPYRIGHT).
Rust 1.99.1's [target build script](https://github.com/rust-lang/rust/blob/1.99.1/src/ci/docker/scripts/musl-toolchain.sh)
selects musl 1.2.5 with security patches. The vendored notice is from the
[musl 1.2.5 source](https://git.musl-libc.org/cgit/musl/plain/COPYRIGHT?h=v1.2.5), SHA-256
`f9bc4423732350eb0b3f7ed7e91d530298476f8fec0c6c427a1c04ade22655af`.
Review the runtime inventory when changing the toolchain or target rather than relying on Cargo
dependency notices alone. Windows builds use Microsoft's static CRT under the build tools' terms;
Windows system DLLs are supplied by the operating system.
