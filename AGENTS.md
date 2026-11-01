# FCO Market workspace

Use this existing source directory for all edits. Do not create versioned copies or new repair folders.

Build with build.bat (scripts/build.ps1). It verifies the new EXE before publishing it to release/ and Downloads, then removes older FCO executables and generated build/cache directories. Never delete FCO-Market-3-data or source files as part of build cleanup. Keep previous executables when a build or verification fails. Use -VerifyOnly to validate packaging without replacing published executables.

Use build.bat -Plan to inspect the output and cleanup scope without building or deleting files.
