{
  description = "daily — Daily Problems CLI (download inputs and submit answers)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { self, nixpkgs }:
    let
      # Systems we build for.
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      # The package itself. Standard-library-only Python app built with hatchling.
      packages = forAllSystems (pkgs: rec {
        daily-problems-cli = pkgs.python3Packages.buildPythonApplication {
          pname = "daily-problems-cli";
          version = "0.1.0";
          pyproject = true;

          src = self;

          build-system = [ pkgs.python3Packages.hatchling ];

          # No runtime dependencies — standard library only.
          dependencies = [ ];

          nativeCheckInputs = [ pkgs.python3Packages.pytest ];

          meta = {
            description = "Command-line client for Daily Problems: download inputs and submit answers";
            homepage = "https://github.com/kuhaku-space/daily-problems-cli";
            license = pkgs.lib.licenses.mit;
            mainProgram = "daily";
          };
        };

        default = daily-problems-cli;
      });

      # Overlay so consumers can pull `daily-problems-cli` into their own nixpkgs.
      overlays.default = final: prev: {
        daily-problems-cli = self.packages.${final.system}.daily-problems-cli;
      };

      # `nix run` / `nix run .#daily`
      apps = forAllSystems (pkgs: {
        default = {
          type = "app";
          program = "${self.packages.${pkgs.system}.daily-problems-cli}/bin/daily";
        };
      });

      # Dev shell for working on this repo (`nix develop`).
      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          packages = [
            pkgs.uv
            (pkgs.python3.withPackages (ps: [ ps.pytest ]))
          ];
        };
      });
    };
}
