{
  pkgs,
  lib,
  config,
  inputs,
  ...
}: {
  languages.python = {
    enable = true;
    version = "3.13";
    venv = {
      enable = true;
      requirements = ./requirements.txt;
    };
  };

  dotenv.enable = true;

  enterShell = ''
    echo ".___                       ___________                            .___"
    echo "|   |______  ____   ____   \_   _____/__________  ____   ____   __| _/"
    echo "|   \_  __ \/  _ \ /    \   |    __)/  _ \_  __ \/ ___\_/ __ \ / __ | "
    echo "|   ||  | \(  <_> )   |  \  |     \(  <_> )  | \/ /_/  >  ___// /_/ | "
    echo "|___||__|   \____/|___|  /  \___  / \____/|__|  \___  / \___  >____ | "
    echo "                       \/       \/             /_____/      \/     \/"
  '';
}
