import Lake
open Lake DSL

package «probe_tests» where
  version := v!"0.1.0"

require aesop from git
  "https://github.com/leanprover-community/aesop" @ "v4.15.0"

lean_lib «ProbeTests» where
  -- add library configuration options here

@[default_target]
lean_exe «probe_tests» where
  root := `Main
