{pkgs, ...}: {
  languages.python = {
    enable = true;
    package = pkgs.python313;

    venv = {
      enable = true;
      requirements = builtins.readFile ./requirements.txt;
    };
  };
}
